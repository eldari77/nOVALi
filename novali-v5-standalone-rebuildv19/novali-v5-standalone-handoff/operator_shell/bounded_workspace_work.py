from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import Any

from .common import OPERATOR_POLICY_ROOT_ENV


WORK_SUMMARY_SCHEMA_NAME = "GovernedExecutionWorkSummary"
WORK_SUMMARY_SCHEMA_VERSION = "governed_execution_work_summary_v1"
FILE_PLAN_SCHEMA_NAME = "GovernedExecutionFilePlan"
FILE_PLAN_SCHEMA_VERSION = "governed_execution_file_plan_v1"
IMPLEMENTATION_BUNDLE_SCHEMA_NAME = "GovernedExecutionImplementationBundleSummary"
IMPLEMENTATION_BUNDLE_SCHEMA_VERSION = "governed_execution_implementation_bundle_summary_v1"
WORKSPACE_ARTIFACT_INDEX_SCHEMA_NAME = "GovernedExecutionWorkspaceArtifactIndex"
WORKSPACE_ARTIFACT_INDEX_SCHEMA_VERSION = "governed_execution_workspace_artifact_index_v1"
CONTROLLER_SUMMARY_SCHEMA_NAME = "GovernedExecutionControllerSummary"
CONTROLLER_SUMMARY_SCHEMA_VERSION = "governed_execution_controller_summary_v1"
SUCCESSOR_READINESS_EVALUATION_SCHEMA_NAME = "GovernedExecutionSuccessorReadinessEvaluation"
SUCCESSOR_READINESS_EVALUATION_SCHEMA_VERSION = "governed_execution_successor_readiness_evaluation_v1"
SUCCESSOR_DELIVERY_MANIFEST_SCHEMA_NAME = "GovernedExecutionSuccessorDeliveryManifest"
SUCCESSOR_DELIVERY_MANIFEST_SCHEMA_VERSION = "governed_execution_successor_delivery_manifest_v1"
TRUSTED_PLANNING_EVIDENCE_SCHEMA_NAME = "GovernedExecutionTrustedPlanningEvidence"
TRUSTED_PLANNING_EVIDENCE_SCHEMA_VERSION = "governed_execution_trusted_planning_evidence_v1"
MISSING_DELIVERABLES_SCHEMA_NAME = "GovernedExecutionMissingDeliverablesSummary"
MISSING_DELIVERABLES_SCHEMA_VERSION = "governed_execution_missing_deliverables_summary_v1"
NEXT_STEP_DERIVATION_SCHEMA_NAME = "GovernedExecutionNextStepDerivation"
NEXT_STEP_DERIVATION_SCHEMA_VERSION = "governed_execution_next_step_derivation_v1"
COMPLETION_EVALUATION_SCHEMA_NAME = "GovernedExecutionCompletionEvaluation"
COMPLETION_EVALUATION_SCHEMA_VERSION = "governed_execution_completion_evaluation_v1"
SUCCESSOR_REVIEW_SUMMARY_SCHEMA_NAME = "GovernedExecutionSuccessorReviewSummary"
SUCCESSOR_REVIEW_SUMMARY_SCHEMA_VERSION = "governed_execution_successor_review_summary_v1"
SUCCESSOR_PROMOTION_RECOMMENDATION_SCHEMA_NAME = "GovernedExecutionSuccessorPromotionRecommendation"
SUCCESSOR_PROMOTION_RECOMMENDATION_SCHEMA_VERSION = "governed_execution_successor_promotion_recommendation_v1"
SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME = "GovernedExecutionSuccessorNextObjectiveProposal"
SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION = "governed_execution_successor_next_objective_proposal_v1"
SUCCESSOR_RESEED_REQUEST_SCHEMA_NAME = "GovernedExecutionSuccessorReseedRequest"
SUCCESSOR_RESEED_REQUEST_SCHEMA_VERSION = "governed_execution_successor_reseed_request_v1"
SUCCESSOR_RESEED_DECISION_SCHEMA_NAME = "GovernedExecutionSuccessorReseedDecision"
SUCCESSOR_RESEED_DECISION_SCHEMA_VERSION = "governed_execution_successor_reseed_decision_v1"
SUCCESSOR_CONTINUATION_LINEAGE_SCHEMA_NAME = "GovernedExecutionSuccessorContinuationLineage"
SUCCESSOR_CONTINUATION_LINEAGE_SCHEMA_VERSION = "governed_execution_successor_continuation_lineage_v1"
SUCCESSOR_EFFECTIVE_NEXT_OBJECTIVE_SCHEMA_NAME = "GovernedExecutionSuccessorEffectiveNextObjective"
SUCCESSOR_EFFECTIVE_NEXT_OBJECTIVE_SCHEMA_VERSION = "governed_execution_successor_effective_next_objective_v1"
SUCCESSOR_AUTO_CONTINUE_POLICY_SCHEMA_NAME = "GovernedExecutionSuccessorAutoContinuePolicy"
SUCCESSOR_AUTO_CONTINUE_POLICY_SCHEMA_VERSION = "governed_execution_successor_auto_continue_policy_v1"
SUCCESSOR_AUTO_CONTINUE_STATE_SCHEMA_NAME = "GovernedExecutionSuccessorAutoContinueState"
SUCCESSOR_AUTO_CONTINUE_STATE_SCHEMA_VERSION = "governed_execution_successor_auto_continue_state_v1"
SUCCESSOR_AUTO_CONTINUE_DECISION_SCHEMA_NAME = "GovernedExecutionSuccessorAutoContinueDecision"
SUCCESSOR_AUTO_CONTINUE_DECISION_SCHEMA_VERSION = "governed_execution_successor_auto_continue_decision_v1"
SUCCESSOR_CANDIDATE_PROMOTION_BUNDLE_SCHEMA_NAME = "GovernedExecutionSuccessorCandidatePromotionBundle"
SUCCESSOR_CANDIDATE_PROMOTION_BUNDLE_SCHEMA_VERSION = "governed_execution_successor_candidate_promotion_bundle_v1"
SUCCESSOR_BASELINE_ADMISSION_REVIEW_SCHEMA_NAME = "GovernedExecutionSuccessorBaselineAdmissionReview"
SUCCESSOR_BASELINE_ADMISSION_REVIEW_SCHEMA_VERSION = "governed_execution_successor_baseline_admission_review_v1"
SUCCESSOR_BASELINE_ADMISSION_RECOMMENDATION_SCHEMA_NAME = "GovernedExecutionSuccessorBaselineAdmissionRecommendation"
SUCCESSOR_BASELINE_ADMISSION_RECOMMENDATION_SCHEMA_VERSION = "governed_execution_successor_baseline_admission_recommendation_v1"
SUCCESSOR_BASELINE_ADMISSION_DECISION_SCHEMA_NAME = "GovernedExecutionSuccessorBaselineAdmissionDecision"
SUCCESSOR_BASELINE_ADMISSION_DECISION_SCHEMA_VERSION = "governed_execution_successor_baseline_admission_decision_v1"
SUCCESSOR_BASELINE_REMEDIATION_PROPOSAL_SCHEMA_NAME = "GovernedExecutionSuccessorBaselineRemediationProposal"
SUCCESSOR_BASELINE_REMEDIATION_PROPOSAL_SCHEMA_VERSION = "governed_execution_successor_baseline_remediation_proposal_v1"
SUCCESSOR_ADMITTED_CANDIDATE_SCHEMA_NAME = "GovernedExecutionSuccessorAdmittedCandidate"
SUCCESSOR_ADMITTED_CANDIDATE_SCHEMA_VERSION = "governed_execution_successor_admitted_candidate_v1"
SUCCESSOR_ADMITTED_CANDIDATE_HANDOFF_SCHEMA_NAME = "GovernedExecutionSuccessorAdmittedCandidateHandoff"
SUCCESSOR_ADMITTED_CANDIDATE_HANDOFF_SCHEMA_VERSION = "governed_execution_successor_admitted_candidate_handoff_v1"
SUCCESSOR_BASELINE_COMPARISON_SCHEMA_NAME = "GovernedExecutionSuccessorBaselineComparison"
SUCCESSOR_BASELINE_COMPARISON_SCHEMA_VERSION = "governed_execution_successor_baseline_comparison_v1"
SUCCESSOR_REFERENCE_TARGET_SCHEMA_NAME = "GovernedExecutionSuccessorReferenceTarget"
SUCCESSOR_REFERENCE_TARGET_SCHEMA_VERSION = "governed_execution_successor_reference_target_v1"
SUCCESSOR_REFERENCE_TARGET_CONSUMPTION_SCHEMA_NAME = "GovernedExecutionSuccessorReferenceTargetConsumption"
SUCCESSOR_REFERENCE_TARGET_CONSUMPTION_SCHEMA_VERSION = "governed_execution_successor_reference_target_consumption_v1"
SUCCESSOR_SKILL_PACK_INVOCATION_SCHEMA_NAME = "GovernedExecutionSuccessorSkillPackInvocation"
SUCCESSOR_SKILL_PACK_INVOCATION_SCHEMA_VERSION = "governed_execution_successor_skill_pack_invocation_v1"
SUCCESSOR_SKILL_PACK_RESULT_SCHEMA_NAME = "GovernedExecutionSuccessorSkillPackResult"
SUCCESSOR_SKILL_PACK_RESULT_SCHEMA_VERSION = "governed_execution_successor_skill_pack_result_v1"
SUCCESSOR_QUALITY_GAP_SUMMARY_SCHEMA_NAME = "GovernedExecutionSuccessorQualityGapSummary"
SUCCESSOR_QUALITY_GAP_SUMMARY_SCHEMA_VERSION = "governed_execution_successor_quality_gap_summary_v1"
SUCCESSOR_QUALITY_IMPROVEMENT_SUMMARY_SCHEMA_NAME = "GovernedExecutionSuccessorQualityImprovementSummary"
SUCCESSOR_QUALITY_IMPROVEMENT_SUMMARY_SCHEMA_VERSION = "governed_execution_successor_quality_improvement_summary_v1"
SUCCESSOR_QUALITY_ROADMAP_SCHEMA_NAME = "GovernedExecutionSuccessorQualityRoadmap"
SUCCESSOR_QUALITY_ROADMAP_SCHEMA_VERSION = "governed_execution_successor_quality_roadmap_v1"
SUCCESSOR_QUALITY_PRIORITY_MATRIX_SCHEMA_NAME = "GovernedExecutionSuccessorQualityPriorityMatrix"
SUCCESSOR_QUALITY_PRIORITY_MATRIX_SCHEMA_VERSION = "governed_execution_successor_quality_priority_matrix_v1"
SUCCESSOR_QUALITY_COMPOSITE_EVALUATION_SCHEMA_NAME = "GovernedExecutionSuccessorQualityCompositeEvaluation"
SUCCESSOR_QUALITY_COMPOSITE_EVALUATION_SCHEMA_VERSION = "governed_execution_successor_quality_composite_evaluation_v1"
SUCCESSOR_QUALITY_NEXT_PACK_PLAN_SCHEMA_NAME = "GovernedExecutionSuccessorQualityNextPackPlan"
SUCCESSOR_QUALITY_NEXT_PACK_PLAN_SCHEMA_VERSION = "governed_execution_successor_quality_next_pack_plan_v1"
SUCCESSOR_QUALITY_CHAIN_REENTRY_SCHEMA_NAME = "GovernedExecutionSuccessorQualityChainReentry"
SUCCESSOR_QUALITY_CHAIN_REENTRY_SCHEMA_VERSION = "governed_execution_successor_quality_chain_reentry_v1"
SUCCESSOR_GENERATION_HISTORY_SCHEMA_NAME = "GovernedExecutionSuccessorGenerationHistory"
SUCCESSOR_GENERATION_HISTORY_SCHEMA_VERSION = "governed_execution_successor_generation_history_v1"
SUCCESSOR_GENERATION_DELTA_SCHEMA_NAME = "GovernedExecutionSuccessorGenerationDelta"
SUCCESSOR_GENERATION_DELTA_SCHEMA_VERSION = "governed_execution_successor_generation_delta_v1"
SUCCESSOR_PROGRESS_GOVERNANCE_SCHEMA_NAME = "GovernedExecutionSuccessorProgressGovernance"
SUCCESSOR_PROGRESS_GOVERNANCE_SCHEMA_VERSION = "governed_execution_successor_progress_governance_v1"
SUCCESSOR_PROGRESS_RECOMMENDATION_SCHEMA_NAME = "GovernedExecutionSuccessorProgressRecommendation"
SUCCESSOR_PROGRESS_RECOMMENDATION_SCHEMA_VERSION = "governed_execution_successor_progress_recommendation_v1"
SUCCESSOR_STRATEGY_SELECTION_SCHEMA_NAME = "GovernedExecutionSuccessorStrategySelection"
SUCCESSOR_STRATEGY_SELECTION_SCHEMA_VERSION = "governed_execution_successor_strategy_selection_v1"
SUCCESSOR_STRATEGY_RATIONALE_SCHEMA_NAME = "GovernedExecutionSuccessorStrategyRationale"
SUCCESSOR_STRATEGY_RATIONALE_SCHEMA_VERSION = "governed_execution_successor_strategy_rationale_v1"
SUCCESSOR_STRATEGY_FOLLOW_ON_PLAN_SCHEMA_NAME = "GovernedExecutionSuccessorStrategyFollowOnPlan"
SUCCESSOR_STRATEGY_FOLLOW_ON_PLAN_SCHEMA_VERSION = "governed_execution_successor_strategy_follow_on_plan_v1"
SUCCESSOR_STRATEGY_DECISION_SUPPORT_SCHEMA_NAME = "GovernedExecutionSuccessorStrategyDecisionSupport"
SUCCESSOR_STRATEGY_DECISION_SUPPORT_SCHEMA_VERSION = "governed_execution_successor_strategy_decision_support_v1"
SUCCESSOR_CAMPAIGN_HISTORY_SCHEMA_NAME = "GovernedExecutionSuccessorCampaignHistory"
SUCCESSOR_CAMPAIGN_HISTORY_SCHEMA_VERSION = "governed_execution_successor_campaign_history_v1"
SUCCESSOR_CAMPAIGN_DELTA_SCHEMA_NAME = "GovernedExecutionSuccessorCampaignDelta"
SUCCESSOR_CAMPAIGN_DELTA_SCHEMA_VERSION = "governed_execution_successor_campaign_delta_v1"
SUCCESSOR_CAMPAIGN_GOVERNANCE_SCHEMA_NAME = "GovernedExecutionSuccessorCampaignGovernance"
SUCCESSOR_CAMPAIGN_GOVERNANCE_SCHEMA_VERSION = "governed_execution_successor_campaign_governance_v1"
SUCCESSOR_CAMPAIGN_RECOMMENDATION_SCHEMA_NAME = "GovernedExecutionSuccessorCampaignRecommendation"
SUCCESSOR_CAMPAIGN_RECOMMENDATION_SCHEMA_VERSION = "governed_execution_successor_campaign_recommendation_v1"
SUCCESSOR_CAMPAIGN_WAVE_PLAN_SCHEMA_NAME = "GovernedExecutionSuccessorCampaignWavePlan"
SUCCESSOR_CAMPAIGN_WAVE_PLAN_SCHEMA_VERSION = "governed_execution_successor_campaign_wave_plan_v1"
SUCCESSOR_CAMPAIGN_CYCLE_HISTORY_SCHEMA_NAME = "GovernedExecutionSuccessorCampaignCycleHistory"
SUCCESSOR_CAMPAIGN_CYCLE_HISTORY_SCHEMA_VERSION = "governed_execution_successor_campaign_cycle_history_v1"
SUCCESSOR_CAMPAIGN_CYCLE_DELTA_SCHEMA_NAME = "GovernedExecutionSuccessorCampaignCycleDelta"
SUCCESSOR_CAMPAIGN_CYCLE_DELTA_SCHEMA_VERSION = "governed_execution_successor_campaign_cycle_delta_v1"
SUCCESSOR_CAMPAIGN_CYCLE_GOVERNANCE_SCHEMA_NAME = "GovernedExecutionSuccessorCampaignCycleGovernance"
SUCCESSOR_CAMPAIGN_CYCLE_GOVERNANCE_SCHEMA_VERSION = "governed_execution_successor_campaign_cycle_governance_v1"
SUCCESSOR_CAMPAIGN_CYCLE_RECOMMENDATION_SCHEMA_NAME = "GovernedExecutionSuccessorCampaignCycleRecommendation"
SUCCESSOR_CAMPAIGN_CYCLE_RECOMMENDATION_SCHEMA_VERSION = "governed_execution_successor_campaign_cycle_recommendation_v1"
SUCCESSOR_CAMPAIGN_CYCLE_FOLLOW_ON_PLAN_SCHEMA_NAME = "GovernedExecutionSuccessorCampaignCycleFollowOnPlan"
SUCCESSOR_CAMPAIGN_CYCLE_FOLLOW_ON_PLAN_SCHEMA_VERSION = "governed_execution_successor_campaign_cycle_follow_on_plan_v1"
SUCCESSOR_LOOP_HISTORY_SCHEMA_NAME = "GovernedExecutionSuccessorLoopHistory"
SUCCESSOR_LOOP_HISTORY_SCHEMA_VERSION = "governed_execution_successor_loop_history_v1"
SUCCESSOR_LOOP_DELTA_SCHEMA_NAME = "GovernedExecutionSuccessorLoopDelta"
SUCCESSOR_LOOP_DELTA_SCHEMA_VERSION = "governed_execution_successor_loop_delta_v1"
SUCCESSOR_LOOP_GOVERNANCE_SCHEMA_NAME = "GovernedExecutionSuccessorLoopGovernance"
SUCCESSOR_LOOP_GOVERNANCE_SCHEMA_VERSION = "governed_execution_successor_loop_governance_v1"
SUCCESSOR_LOOP_RECOMMENDATION_SCHEMA_NAME = "GovernedExecutionSuccessorLoopRecommendation"
SUCCESSOR_LOOP_RECOMMENDATION_SCHEMA_VERSION = "governed_execution_successor_loop_recommendation_v1"
SUCCESSOR_LOOP_FOLLOW_ON_PLAN_SCHEMA_NAME = "GovernedExecutionSuccessorLoopFollowOnPlan"
SUCCESSOR_LOOP_FOLLOW_ON_PLAN_SCHEMA_VERSION = "governed_execution_successor_loop_follow_on_plan_v1"
SUCCESSOR_REVISED_CANDIDATE_BUNDLE_SCHEMA_NAME = "GovernedExecutionSuccessorRevisedCandidateBundle"
SUCCESSOR_REVISED_CANDIDATE_BUNDLE_SCHEMA_VERSION = "governed_execution_successor_revised_candidate_bundle_v1"
SUCCESSOR_REVISED_CANDIDATE_HANDOFF_SCHEMA_NAME = "GovernedExecutionSuccessorRevisedCandidateHandoff"
SUCCESSOR_REVISED_CANDIDATE_HANDOFF_SCHEMA_VERSION = "governed_execution_successor_revised_candidate_handoff_v1"
SUCCESSOR_REVISED_CANDIDATE_COMPARISON_SCHEMA_NAME = "GovernedExecutionSuccessorRevisedCandidateComparison"
SUCCESSOR_REVISED_CANDIDATE_COMPARISON_SCHEMA_VERSION = "governed_execution_successor_revised_candidate_comparison_v1"
SUCCESSOR_REVISED_CANDIDATE_PROMOTION_SUMMARY_SCHEMA_NAME = "GovernedExecutionSuccessorRevisedCandidatePromotionSummary"
SUCCESSOR_REVISED_CANDIDATE_PROMOTION_SUMMARY_SCHEMA_VERSION = "governed_execution_successor_revised_candidate_promotion_summary_v1"
SUCCESSOR_COMPLETION_KNOWLEDGE_PACK_SCHEMA_NAME = "NovaliSuccessorCompletionKnowledgePack"
SUCCESSOR_COMPLETION_KNOWLEDGE_PACK_SCHEMA_VERSION = "novali_successor_completion_knowledge_pack_v1"
WORKSPACE_CONTINUATION_KNOWLEDGE_PACK_SCHEMA_NAME = "NovaliWorkspaceContinuationKnowledgePack"
WORKSPACE_CONTINUATION_KNOWLEDGE_PACK_SCHEMA_VERSION = "novali_workspace_continuation_knowledge_pack_v1"
SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_NAME = "NovaliSuccessorPromotionReviewKnowledgePack"
SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_VERSION = "novali_successor_promotion_review_knowledge_pack_v1"
SUCCESSOR_BASELINE_ADMISSION_KNOWLEDGE_PACK_SCHEMA_NAME = "NovaliSuccessorBaselineAdmissionKnowledgePack"
SUCCESSOR_BASELINE_ADMISSION_KNOWLEDGE_PACK_SCHEMA_VERSION = "novali_successor_baseline_admission_knowledge_pack_v1"
SUCCESSOR_ADMITTED_CANDIDATE_COMPARISON_KNOWLEDGE_PACK_SCHEMA_NAME = "NovaliSuccessorAdmittedCandidateComparisonKnowledgePack"
SUCCESSOR_ADMITTED_CANDIDATE_COMPARISON_KNOWLEDGE_PACK_SCHEMA_VERSION = "novali_successor_admitted_candidate_comparison_knowledge_pack_v1"
SUCCESSOR_SKILL_PACK_MANIFEST_SCHEMA_NAME = "NovaliBoundedSkillPackManifest"
SUCCESSOR_SKILL_PACK_MANIFEST_SCHEMA_VERSION = "novali_bounded_skill_pack_manifest_v1"
INTERNAL_SUCCESSOR_COMPLETION_SOURCE_ID = "internal_knowledge_pack:successor_completion_v1"
INTERNAL_WORKSPACE_CONTINUATION_SOURCE_ID = "internal_knowledge_pack:workspace_continuation_v1"
INTERNAL_SUCCESSOR_PROMOTION_REVIEW_SOURCE_ID = "internal_knowledge_pack:successor_promotion_review_v1"
INTERNAL_SUCCESSOR_BASELINE_ADMISSION_SOURCE_ID = "internal_knowledge_pack:successor_baseline_admission_v1"
INTERNAL_SUCCESSOR_ADMITTED_CANDIDATE_COMPARISON_SOURCE_ID = "internal_knowledge_pack:successor_admitted_candidate_comparison_v1"
INTERNAL_SUCCESSOR_WORKSPACE_REVIEW_SKILL_PACK_ID = "successor_workspace_review_pack_v1"
INTERNAL_SUCCESSOR_TEST_STRENGTHENING_SKILL_PACK_ID = "successor_test_strengthening_pack_v1"
INTERNAL_SUCCESSOR_MANIFEST_QUALITY_SKILL_PACK_ID = "successor_manifest_quality_pack_v1"
INTERNAL_SUCCESSOR_DOCS_READINESS_SKILL_PACK_ID = "successor_docs_readiness_pack_v1"
INTERNAL_SUCCESSOR_ARTIFACT_INDEX_CONSISTENCY_SKILL_PACK_ID = "successor_artifact_index_consistency_pack_v1"
INTERNAL_SUCCESSOR_HANDOFF_COMPLETENESS_SKILL_PACK_ID = "successor_handoff_completeness_pack_v1"
CYCLE_EXECUTION_MODEL = "single_cycle_per_governed_execution_invocation"
MULTI_CYCLE_EXECUTION_MODEL = "multi_cycle_bounded_governed_execution"
STOP_REASON_COMPLETED = "completed_by_directive_stop_condition"
STOP_REASON_NO_WORK = "no_admissible_bounded_work"
STOP_REASON_BLOCKED = "blocked_by_policy"
STOP_REASON_FAILURE = "bounded_failure"
STOP_REASON_MAX_CAP = "max_cycle_cap_reached"
STOP_REASON_SINGLE_CYCLE = "single_cycle_invocation_completed"
SUCCESSOR_COMPLETION_RULE = "all_required_deliverables_present_inside_active_workspace"
REVIEW_STATUS_REQUIRED = "review_required"
PROMOTION_RECOMMENDED_STATE = "promotion_recommended"
PROMOTION_NOT_RECOMMENDED_STATE = "promotion_not_recommended"
NEXT_OBJECTIVE_AVAILABLE_STATE = "next_objective_available"
PROMOTION_DEFERRED_STATE = "promotion_deferred"
ADMISSION_REVIEW_REQUIRED_STATE = "admission_review_required"
ADMISSION_RECOMMENDED_STATE = "admission_recommended"
ADMISSION_NOT_RECOMMENDED_STATE = "admission_not_recommended"
ADMISSION_DEFERRED_STATE = "admission_deferred"
BASELINE_CANDIDATE_READY_STATE = "baseline_candidate_ready"
REMEDIATION_REQUIRED_STATE = "remediation_required"
CANDIDATE_NOT_ADMITTED_STATE = "candidate_not_admitted"
ADMITTED_CANDIDATE_RECORDED_STATE = "admitted_candidate_recorded"
HANDOFF_NOT_APPLICABLE_STATE = "handoff_not_applicable_until_admission"
HANDOFF_NOT_READY_STATE = "handoff_not_ready"
ADMITTED_CANDIDATE_HANDOFF_READY_STATE = "admitted_candidate_handoff_ready"
COMPARISON_COMPLETE_STATE = "comparison_complete"
COMPARISON_NOT_APPLICABLE_STATE = "comparison_not_applicable_until_admission"
STRONGER_THAN_CURRENT_BOUNDED_BASELINE_STATE = "stronger_than_current_bounded_baseline"
NOT_STRONGER_ENOUGH_YET_STATE = "not_stronger_enough_yet"
FUTURE_REFERENCE_TARGET_NOT_APPLICABLE_STATE = "future_reference_target_not_applicable_until_admission"
FUTURE_REFERENCE_TARGET_DEFERRED_STATE = "future_reference_target_deferred"
ELIGIBLE_AS_FUTURE_REFERENCE_TARGET_STATE = "eligible_as_future_reference_target"
REFERENCE_TARGET_CONSUMED_STATE = "reference_target_consumed"
REFERENCE_TARGET_MISSING_STATE = "reference_target_missing"
REFERENCE_TARGET_INCOMPATIBLE_STATE = "reference_target_incompatible"
REFERENCE_TARGET_FALLBACK_PROTECTED_BASELINE_STATE = "reference_target_fallback_to_protected_baseline"
QUALITY_DIMENSION_WEAK_STATE = "weak"
QUALITY_DIMENSION_PARTIAL_STATE = "partial"
QUALITY_DIMENSION_RESOLVED_STATE = "resolved"
QUALITY_COMPOSITE_NOT_YET_STRONGER_STATE = "not_yet_materially_stronger"
QUALITY_COMPOSITE_SINGLE_DIMENSION_STATE = "materially_stronger_on_single_dimension"
QUALITY_COMPOSITE_MULTI_DIMENSION_STATE = "materially_stronger_on_multiple_dimensions"
QUALITY_CHAIN_REENTRY_NOT_APPLICABLE_STATE = "not_applicable"
QUALITY_CHAIN_REENTRY_READY_STATE = "ready_for_quality_reentry"
QUALITY_CHAIN_STAGED_FOLLOW_ON_READY_STATE = "staged_quality_follow_on_ready"
QUALITY_CHAIN_DEFERRED_DUE_TO_CYCLE_BUDGET_STATE = "deferred_to_next_invocation_due_to_cycle_budget"
QUALITY_CHAIN_REVIEW_REQUIRED_STATE = "review_required_before_quality_reentry"
QUALITY_CHAIN_NO_FURTHER_WORK_STATE = "no_further_quality_work_staged"
QUALITY_CHAIN_CONTINUED_IN_SESSION_STATE = "quality_follow_on_continued_in_session"
REVISED_CANDIDATE_RECORDED_STATE = "revised_candidate_recorded"
REVISED_CANDIDATE_ADMITTED_STATE = "revised_candidate_admitted"
REVISED_CANDIDATE_DEFERRED_STATE = "revised_candidate_deferred"
REVISED_CANDIDATE_REMEDIATION_REQUIRED_STATE = "revised_candidate_remediation_required"
GENERATIONAL_IMPROVEMENT_CONFIRMED_STATE = "generational_improvement_confirmed"
GENERATIONAL_IMPROVEMENT_PARTIAL_STATE = "generational_improvement_partial"
GENERATIONAL_STAGNATION_DETECTED_STATE = "generational_stagnation_detected"
GENERATIONAL_CHURN_DETECTED_STATE = "generational_churn_detected"
GENERATIONAL_REGRESSION_DETECTED_STATE = "generational_regression_detected"
PROGRESS_RECOMMENDATION_CONTINUE_STATE = "continue_bounded_improvement"
PROGRESS_RECOMMENDATION_REMEDIATE_STATE = "continue_with_targeted_remediation"
PROGRESS_RECOMMENDATION_PAUSE_STATE = "pause_for_operator_review"
PROGRESS_RECOMMENDATION_ESCALATE_STATE = "escalate_for_candidate_review"
PROGRESS_RECOMMENDATION_HOLD_STATE = "hold_current_reference_target"
STRATEGY_CONTINUE_REFINING_CURRENT_REFERENCE_TARGET_STATE = (
    "continue_refining_current_reference_target"
)
STRATEGY_OPEN_TARGETED_REMEDIATION_WAVE_STATE = "open_targeted_remediation_wave"
STRATEGY_START_NEXT_QUALITY_WAVE_STATE = "start_next_quality_wave"
STRATEGY_PAUSE_FOR_OPERATOR_REVIEW_STATE = "pause_for_operator_review"
STRATEGY_HOLD_CURRENT_REFERENCE_TARGET_STATE = "hold_current_reference_target"
STRATEGY_HOLD_AND_OBSERVE_BEFORE_FURTHER_CHANGE_STATE = (
    "hold_and_observe_before_further_change"
)
STRATEGY_FOLLOW_ON_REFINEMENT_WAVE = "successor_quality_refinement_wave"
STRATEGY_FOLLOW_ON_TARGETED_REMEDIATION_WAVE = (
    "targeted_quality_remediation_wave"
)
STRATEGY_FOLLOW_ON_NEXT_QUALITY_WAVE = "broader_successor_quality_wave"
STRATEGY_FOLLOW_ON_PENDING_OPERATOR_REVIEW = "none_pending_operator_review"
STRATEGY_FOLLOW_ON_HOLD_CURRENT_REFERENCE = "none_hold_current_reference_target"
STRATEGY_FOLLOW_ON_HOLD_AND_OBSERVE = "hold_and_observe_before_further_change"
CAMPAIGN_PROGRESS_CONTINUES_STATE = "campaign_meaningful_progress_continues"
CAMPAIGN_PARTIAL_PROGRESS_STATE = "campaign_partial_progress"
CAMPAIGN_DIMINISHING_RETURNS_STATE = "campaign_diminishing_returns_detected"
CAMPAIGN_CONVERGENCE_STATE = "campaign_convergence_detected"
CAMPAIGN_STAGNATION_STATE = "campaign_stagnation_detected"
CAMPAIGN_REGRESSION_STATE = "campaign_regression_detected"
CAMPAIGN_CONTINUE_CURRENT_WAVE_FAMILY_STATE = "campaign_continue_current_wave_family"
CAMPAIGN_SHIFT_TO_TARGETED_REMEDIATION_STATE = (
    "campaign_shift_to_targeted_remediation"
)
CAMPAIGN_START_NEXT_QUALITY_WAVE_STATE = "campaign_start_next_quality_wave"
CAMPAIGN_REFRESH_REVISED_CANDIDATE_STATE = "campaign_refresh_revised_candidate"
CAMPAIGN_PAUSE_FOR_OPERATOR_REVIEW_STATE = "campaign_pause_for_operator_review"
CAMPAIGN_HOLD_CURRENT_REFERENCE_TARGET_STATE = (
    "campaign_hold_current_reference_target"
)
CAMPAIGN_CONVERGENCE_DETECTED_STATE = "campaign_convergence_detected"
CAMPAIGN_RECOMMENDATION_CONTINUE_STATE = "continue_current_campaign"
CAMPAIGN_RECOMMENDATION_REMEDIATE_STATE = (
    "shift_to_targeted_remediation_wave"
)
CAMPAIGN_RECOMMENDATION_NEXT_QUALITY_WAVE_STATE = "start_next_quality_wave"
CAMPAIGN_RECOMMENDATION_REFRESH_STATE = "refresh_revised_candidate_now"
CAMPAIGN_RECOMMENDATION_PAUSE_STATE = "pause_for_operator_review"
CAMPAIGN_RECOMMENDATION_HOLD_STATE = (
    "hold_current_reference_target_pending_more_evidence"
)
CAMPAIGN_FOLLOW_ON_CURRENT_WAVE_CONTINUATION = (
    "current_wave_family_continuation"
)
CAMPAIGN_FOLLOW_ON_REVISED_CANDIDATE_REFRESH = "revised_candidate_refresh_wave"
CAMPAIGN_CYCLE_PROGRESS_CONTINUES_STATE = (
    "campaign_cycle_meaningful_progress_continues"
)
CAMPAIGN_CYCLE_PARTIAL_GAIN_STATE = "campaign_cycle_partial_gain"
CAMPAIGN_CYCLE_DIMINISHING_RETURNS_STATE = (
    "campaign_cycle_diminishing_returns_detected"
)
CAMPAIGN_CYCLE_CONVERGENCE_STATE = "campaign_cycle_convergence_confirmed"
CAMPAIGN_CYCLE_STAGNATION_STATE = "campaign_cycle_stagnation_detected"
CAMPAIGN_CYCLE_REGRESSION_STATE = "campaign_cycle_regression_detected"
CAMPAIGN_CYCLE_START_NEXT_CAMPAIGN_STATE = "campaign_cycle_start_next_campaign"
CAMPAIGN_CYCLE_HOLD_NEW_REFERENCE_TARGET_STATE = (
    "campaign_cycle_hold_new_reference_target"
)
CAMPAIGN_CYCLE_TARGETED_POST_ROLLOVER_REMEDIATION_STATE = (
    "campaign_cycle_targeted_post_rollover_remediation"
)
CAMPAIGN_CYCLE_PAUSE_FOR_OPERATOR_REVIEW_STATE = (
    "campaign_cycle_pause_for_operator_review"
)
CAMPAIGN_CYCLE_DIMINISHING_RETURNS_DETECTED_STATE = (
    "campaign_cycle_diminishing_returns_detected"
)
CAMPAIGN_CYCLE_CONVERGENCE_CONFIRMED_STATE = (
    "campaign_cycle_convergence_confirmed"
)
CAMPAIGN_CYCLE_REGRESSION_DETECTED_STATE = (
    "campaign_cycle_regression_detected"
)
CAMPAIGN_CYCLE_RECOMMENDATION_START_STATE = "start_next_campaign_cycle"
CAMPAIGN_CYCLE_RECOMMENDATION_HOLD_STATE = "hold_new_reference_target"
CAMPAIGN_CYCLE_RECOMMENDATION_REMEDIATE_STATE = (
    "open_targeted_post_rollover_remediation"
)
CAMPAIGN_CYCLE_RECOMMENDATION_PAUSE_STATE = "pause_for_operator_review"
CAMPAIGN_CYCLE_RECOMMENDATION_OBSERVE_STATE = (
    "continue_observing_before_new_cycle"
)
CAMPAIGN_CYCLE_FOLLOW_ON_NEXT_CAMPAIGN = "successor_quality_campaign_wave"
CAMPAIGN_CYCLE_FOLLOW_ON_HOLD_NEW_REFERENCE = "none_hold_new_reference_target"
CAMPAIGN_CYCLE_FOLLOW_ON_TARGETED_POST_ROLLOVER_REMEDIATION = (
    "targeted_post_rollover_remediation_wave"
)
CAMPAIGN_CYCLE_FOLLOW_ON_OBSERVE = "none_observe_current_reference_target"
LOOP_PROGRESS_CONTINUES_STATE = "loop_meaningful_progress_continues"
LOOP_PARTIAL_GAIN_STATE = "loop_partial_gain"
LOOP_DIMINISHING_RETURNS_STATE = "loop_diminishing_returns_detected"
LOOP_CONVERGENCE_STATE = "loop_convergence_confirmed"
LOOP_STAGNATION_STATE = "loop_stagnation_detected"
LOOP_REGRESSION_STATE = "loop_regression_detected"
LOOP_START_NEXT_FULL_CAMPAIGN_STATE = "loop_start_next_full_campaign"
LOOP_HOLD_CURRENT_REFERENCE_TARGET_STATE = "loop_hold_current_reference_target"
LOOP_ALLOW_ONLY_TARGETED_REMEDIATION_STATE = (
    "loop_allow_only_targeted_remediation"
)
LOOP_PAUSE_FOR_OPERATOR_REVIEW_STATE = "loop_pause_for_operator_review"
LOOP_DIMINISHING_RETURNS_DETECTED_STATE = "loop_diminishing_returns_detected"
LOOP_CONVERGENCE_CONFIRMED_STATE = "loop_convergence_confirmed"
LOOP_REGRESSION_DETECTED_STATE = "loop_regression_detected"
LOOP_RECOMMENDATION_START_STATE = "start_next_full_loop"
LOOP_RECOMMENDATION_HOLD_STATE = "hold_current_bounded_target"
LOOP_RECOMMENDATION_REMEDIATE_STATE = "allow_only_targeted_remediation"
LOOP_RECOMMENDATION_PAUSE_STATE = "pause_for_operator_review"
LOOP_RECOMMENDATION_OBSERVE_STATE = "continue_observing_before_new_loop"
LOOP_FOLLOW_ON_NEXT_FULL_CAMPAIGN = CAMPAIGN_CYCLE_FOLLOW_ON_NEXT_CAMPAIGN
LOOP_FOLLOW_ON_HOLD_CURRENT_REFERENCE = "none_hold_current_reference_target"
LOOP_FOLLOW_ON_TARGETED_REMEDIATION = (
    CAMPAIGN_CYCLE_FOLLOW_ON_TARGETED_POST_ROLLOVER_REMEDIATION
)
LOOP_FOLLOW_ON_PENDING_OPERATOR_REVIEW = STRATEGY_FOLLOW_ON_PENDING_OPERATOR_REVIEW
LOOP_FOLLOW_ON_OBSERVE = CAMPAIGN_CYCLE_FOLLOW_ON_OBSERVE
RESEED_PENDING_REVIEW_STATE = "reseed_pending_review"
RESEED_APPROVED_STATE = "reseed_approved"
RESEED_REJECTED_STATE = "reseed_rejected"
RESEED_DEFERRED_STATE = "reseed_deferred"
RESEED_MATERIALIZED_STATE = "reseed_materialized"
AUTO_CONTINUE_REASON_DISABLED = "auto_continue_not_enabled"
AUTO_CONTINUE_REASON_NOT_WHITELISTED = "objective_class_not_whitelisted"
AUTO_CONTINUE_REASON_REVIEW_REQUIRED = "operator_review_required"
AUTO_CONTINUE_REASON_MAX_CHAIN_REACHED = "max_auto_continue_chain_reached"
AUTO_CONTINUE_REASON_INCOMPATIBLE_POLICY = "incompatible_runtime_policy"
AUTO_CONTINUE_REASON_AUTHORIZED = "auto_continue_authorized"
AUTO_CONTINUE_REASON_EXECUTED = "auto_continue_executed"
AUTO_CONTINUE_REASON_NO_PROPOSAL = "no_proposed_next_objective"
AUTO_CONTINUE_ORIGIN_MANUAL = "manual_approval"
AUTO_CONTINUE_ORIGIN_POLICY = "policy_auto_continue"
AUTO_CONTINUE_TRANSITION_NOT_STARTED = "authorized_materialized_only"
AUTO_CONTINUE_TRANSITION_STARTED = "same_session_cycle_started"
AUTO_CONTINUE_STAGING_NOT_APPLICABLE = "not_applicable"
AUTO_CONTINUE_STAGING_NEXT_CYCLE = "continued_with_remaining_cycle_budget"
AUTO_CONTINUE_STAGING_COMPACT_FOLLOW_ON = "continued_with_compact_follow_on"
AUTO_CONTINUE_STAGING_DEFERRED_CYCLE_BUDGET = (
    "deferred_to_fresh_invocation_due_to_cycle_budget"
)
AUTO_CONTINUE_STAGING_REVIEW_GATE = "deferred_to_review_gate"
OBJECTIVE_SOURCE_DIRECTIVE = "directive_objective"
OBJECTIVE_SOURCE_APPROVED_RESEED = "approved_reseed_objective"
SUPPORTED_FIRST_WORK_ACTION_CLASSES = {
    "low_risk_shell_change",
    "diagnostic_schema_materialization",
    "append_only_ledger_write",
}
WORKSPACE_ARTIFACT_CATEGORIES = ("plans", "docs", "src", "tests", "artifacts")
AUTO_CONTINUE_OBJECTIVE_CLASSES = (
    "review_and_expand_workspace_local_implementation",
    "strengthen_successor_test_coverage",
    "improve_successor_package_readiness",
    "refine_successor_docs_readiness",
    "refine_successor_artifact_index_consistency",
    "improve_successor_handoff_completeness",
    "refine_operator_observability_bundle",
    "prepare_candidate_promotion_bundle",
)
COMPACT_AUTO_CONTINUE_OBJECTIVE_CLASSES = (
    "prepare_candidate_promotion_bundle",
    "strengthen_successor_test_coverage",
)
SUCCESSOR_SKILL_PACKS_BY_OBJECTIVE_CLASS = {
    "review_and_expand_workspace_local_implementation": INTERNAL_SUCCESSOR_WORKSPACE_REVIEW_SKILL_PACK_ID,
    "strengthen_successor_test_coverage": INTERNAL_SUCCESSOR_TEST_STRENGTHENING_SKILL_PACK_ID,
    "improve_successor_package_readiness": INTERNAL_SUCCESSOR_MANIFEST_QUALITY_SKILL_PACK_ID,
    "refine_successor_docs_readiness": INTERNAL_SUCCESSOR_DOCS_READINESS_SKILL_PACK_ID,
    "refine_successor_artifact_index_consistency": INTERNAL_SUCCESSOR_ARTIFACT_INDEX_CONSISTENCY_SKILL_PACK_ID,
    "improve_successor_handoff_completeness": INTERNAL_SUCCESSOR_HANDOFF_COMPLETENESS_SKILL_PACK_ID,
}


class GovernedExecutionFailure(RuntimeError):
    def __init__(self, message: str, *, session_artifact_path: str = "", summary_artifact_path: str = "") -> None:
        self.session_artifact_path = str(session_artifact_path)
        self.summary_artifact_path = str(summary_artifact_path)
        super().__init__(message)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def session_artifact_path(workspace_root: str | Path) -> Path:
    return Path(workspace_root) / "artifacts" / "governed_execution_session_latest.json"


def load_session_summary(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    return load_json(session_artifact_path(workspace_root))


def controller_artifact_path(workspace_root: str | Path) -> Path:
    return Path(workspace_root) / "artifacts" / "governed_execution_controller_latest.json"


def load_controller_summary(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    return load_json(controller_artifact_path(workspace_root))


def _append_event(log_path: Path, payload: dict[str, Any]) -> None:
    if str(log_path) in {"", "."}:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _event(
    log_path: Path,
    *,
    event_type: str,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    workspace_root: str,
    **extra: Any,
) -> None:
    _append_event(
        log_path,
        {
            "event_type": event_type,
            "timestamp": _now(),
            "session_id": session_id,
            "directive_id": directive_id,
            "execution_profile": execution_profile,
            "workspace_id": workspace_id,
            "workspace_root": workspace_root,
            **dict(extra),
        },
    )


def _write_text(
    path: Path,
    text: str,
    *,
    log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    workspace_root: str,
    work_item_id: str,
    artifact_kind: str,
) -> None:
    _event(
        log_path,
        event_type="file_write_planned",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=workspace_root,
        work_item_id=work_item_id,
        artifact_kind=artifact_kind,
        path=str(path),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _event(
        log_path,
        event_type="file_write_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=workspace_root,
        work_item_id=work_item_id,
        artifact_kind=artifact_kind,
        path=str(path),
        bytes_written=len(text.encode("utf-8")),
    )


def _write_json(path: Path, payload: dict[str, Any], **kwargs: Any) -> None:
    _write_text(path, _dump(payload), **kwargs)


def _relative_to_workspace(workspace_root: Path, path: Path) -> str:
    return path.relative_to(workspace_root).as_posix()


def _is_under_path(candidate: Path, root: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _classify_workspace_artifact(relative_path: str) -> str:
    parts = [part for part in Path(relative_path).parts if part not in {"."}]
    if not parts:
        return "other"
    root = parts[0]
    return root if root in WORKSPACE_ARTIFACT_CATEGORIES else "other"


def _build_workspace_artifact_index_payload(workspace_root: Path) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}
    for path in sorted(workspace_root.rglob("*")):
        if not path.is_file():
            continue
        relative_path = _relative_to_workspace(workspace_root, path)
        category = _classify_workspace_artifact(relative_path)
        category_counts[category] = category_counts.get(category, 0) + 1
        records.append(
            {
                "relative_path": relative_path,
                "category": category,
                "size_bytes": int(path.stat().st_size),
            }
        )
    next_recommended_cycle = "materialize_workspace_local_implementation"
    has_python_source = any(
        item["category"] == "src" and str(item["relative_path"]).endswith(".py")
        for item in records
    )
    has_python_tests = any(
        item["category"] == "tests" and str(item["relative_path"]).endswith(".py")
        for item in records
    )
    has_continuation_gap_analysis = any(
        str(item["relative_path"]) == "plans/successor_continuation_gap_analysis.md"
        for item in records
    )
    has_successor_readiness_bundle = all(
        any(str(item["relative_path"]) == relative_path for item in records)
        for relative_path in (
            "src/successor_shell/successor_manifest.py",
            "tests/test_successor_manifest.py",
            "docs/successor_package_readiness_note.md",
            "artifacts/successor_readiness_evaluation_latest.json",
            "artifacts/successor_delivery_manifest_latest.json",
        )
    )
    if has_successor_readiness_bundle:
        next_recommended_cycle = "operator_review_required"
    elif has_continuation_gap_analysis:
        next_recommended_cycle = "materialize_successor_package_readiness_bundle"
    elif has_python_source and has_python_tests:
        next_recommended_cycle = "plan_successor_package_gap_closure"
    elif has_python_source:
        next_recommended_cycle = "add_workspace_local_tests"
    return {
        "schema_name": WORKSPACE_ARTIFACT_INDEX_SCHEMA_NAME,
        "schema_version": WORKSPACE_ARTIFACT_INDEX_SCHEMA_VERSION,
        "generated_at": _now(),
        "workspace_root": str(workspace_root),
        "artifact_count": len(records),
        "category_counts": category_counts,
        "artifacts": records,
        "next_recommended_cycle": next_recommended_cycle,
    }


def _workspace_paths(workspace_root: Path) -> dict[str, Path]:
    return {
        "docs_root": workspace_root / "docs",
        "src_root": workspace_root / "src",
        "tests_root": workspace_root / "tests",
        "artifacts_root": workspace_root / "artifacts",
        "cycles_root": workspace_root / "artifacts" / "cycles",
        "plans_root": workspace_root / "plans",
        "plan_path": workspace_root / "plans" / "bounded_work_cycle_plan.md",
        "design_path": workspace_root / "docs" / "mutable_shell_successor_design_note.md",
        "src_readme_path": workspace_root / "src" / "README.md",
        "tests_readme_path": workspace_root / "tests" / "README.md",
        "file_plan_path": workspace_root / "artifacts" / "bounded_work_file_plan.json",
        "summary_path": workspace_root / "artifacts" / "bounded_work_summary_latest.json",
        "implementation_summary_path": workspace_root / "artifacts" / "implementation_bundle_summary_latest.json",
        "workspace_artifact_index_path": workspace_root / "artifacts" / "workspace_artifact_index_latest.json",
        "controller_summary_path": workspace_root / "artifacts" / "governed_execution_controller_latest.json",
        "trusted_planning_evidence_path": workspace_root / "artifacts" / "trusted_planning_evidence_latest.json",
        "missing_deliverables_path": workspace_root / "artifacts" / "missing_deliverables_latest.json",
        "next_step_derivation_path": workspace_root / "artifacts" / "next_step_derivation_latest.json",
        "completion_evaluation_path": workspace_root / "artifacts" / "completion_evaluation_latest.json",
        "review_summary_path": workspace_root / "artifacts" / "successor_review_summary_latest.json",
        "promotion_recommendation_path": workspace_root / "artifacts" / "successor_promotion_recommendation_latest.json",
        "next_objective_proposal_path": workspace_root / "artifacts" / "successor_next_objective_proposal_latest.json",
        "reseed_request_path": workspace_root / "artifacts" / "successor_reseed_request_latest.json",
        "reseed_decision_path": workspace_root / "artifacts" / "successor_reseed_decision_latest.json",
        "continuation_lineage_path": workspace_root / "artifacts" / "successor_continuation_lineage_latest.json",
        "effective_next_objective_path": workspace_root / "artifacts" / "successor_effective_next_objective_latest.json",
        "auto_continue_state_path": workspace_root / "artifacts" / "successor_auto_continue_state_latest.json",
        "auto_continue_decision_path": workspace_root / "artifacts" / "successor_auto_continue_decision_latest.json",
        "baseline_admission_review_path": workspace_root / "artifacts" / "successor_baseline_admission_review_latest.json",
        "baseline_admission_recommendation_path": workspace_root / "artifacts" / "successor_baseline_admission_recommendation_latest.json",
        "baseline_admission_decision_path": workspace_root / "artifacts" / "successor_baseline_admission_decision_latest.json",
        "baseline_remediation_proposal_path": workspace_root / "artifacts" / "successor_baseline_remediation_proposal_latest.json",
        "admitted_candidate_path": workspace_root / "artifacts" / "successor_admitted_candidate_latest.json",
        "admitted_candidate_handoff_path": workspace_root / "artifacts" / "successor_admitted_candidate_handoff_latest.json",
        "baseline_comparison_path": workspace_root / "artifacts" / "successor_baseline_comparison_latest.json",
        "reference_target_path": workspace_root / "artifacts" / "successor_reference_target_latest.json",
        "reference_target_consumption_path": workspace_root / "artifacts" / "successor_reference_target_consumption_latest.json",
        "revised_candidate_bundle_path": workspace_root / "artifacts" / "successor_revised_candidate_bundle_latest.json",
        "revised_candidate_handoff_path": workspace_root / "artifacts" / "successor_revised_candidate_handoff_latest.json",
        "revised_candidate_comparison_path": workspace_root / "artifacts" / "successor_revised_candidate_comparison_latest.json",
        "revised_candidate_promotion_summary_path": workspace_root / "artifacts" / "successor_revised_candidate_promotion_summary_latest.json",
        "skill_pack_invocation_path": workspace_root / "artifacts" / "successor_skill_pack_invocation_latest.json",
        "skill_pack_result_path": workspace_root / "artifacts" / "successor_skill_pack_result_latest.json",
        "quality_gap_summary_path": workspace_root / "artifacts" / "successor_quality_gap_summary_latest.json",
        "quality_improvement_summary_path": workspace_root / "artifacts" / "successor_quality_improvement_summary_latest.json",
        "quality_roadmap_path": workspace_root / "artifacts" / "successor_quality_roadmap_latest.json",
        "quality_priority_matrix_path": workspace_root / "artifacts" / "successor_quality_priority_matrix_latest.json",
        "quality_composite_evaluation_path": workspace_root / "artifacts" / "successor_quality_composite_evaluation_latest.json",
        "quality_next_pack_plan_path": workspace_root / "artifacts" / "successor_quality_next_pack_plan_latest.json",
        "quality_chain_reentry_path": workspace_root / "artifacts" / "successor_quality_chain_reentry_latest.json",
        "generation_history_path": workspace_root / "artifacts" / "successor_generation_history_latest.json",
        "generation_delta_path": workspace_root / "artifacts" / "successor_generation_delta_latest.json",
        "progress_governance_path": workspace_root / "artifacts" / "successor_progress_governance_latest.json",
        "progress_recommendation_path": workspace_root / "artifacts" / "successor_progress_recommendation_latest.json",
        "strategy_selection_path": workspace_root / "artifacts" / "successor_strategy_selection_latest.json",
        "strategy_rationale_path": workspace_root / "artifacts" / "successor_strategy_rationale_latest.json",
        "strategy_follow_on_plan_path": workspace_root / "artifacts" / "successor_strategy_follow_on_plan_latest.json",
        "strategy_decision_support_path": workspace_root / "artifacts" / "successor_strategy_decision_support_latest.json",
        "campaign_history_path": workspace_root / "artifacts" / "successor_campaign_history_latest.json",
        "campaign_delta_path": workspace_root / "artifacts" / "successor_campaign_delta_latest.json",
        "campaign_governance_path": workspace_root / "artifacts" / "successor_campaign_governance_latest.json",
        "campaign_recommendation_path": workspace_root / "artifacts" / "successor_campaign_recommendation_latest.json",
        "campaign_wave_plan_path": workspace_root / "artifacts" / "successor_campaign_wave_plan_latest.json",
        "campaign_cycle_history_path": workspace_root / "artifacts" / "successor_campaign_cycle_history_latest.json",
        "campaign_cycle_delta_path": workspace_root / "artifacts" / "successor_campaign_cycle_delta_latest.json",
        "campaign_cycle_governance_path": workspace_root / "artifacts" / "successor_campaign_cycle_governance_latest.json",
        "campaign_cycle_recommendation_path": workspace_root / "artifacts" / "successor_campaign_cycle_recommendation_latest.json",
        "campaign_cycle_follow_on_plan_path": workspace_root / "artifacts" / "successor_campaign_cycle_follow_on_plan_latest.json",
        "loop_history_path": workspace_root / "artifacts" / "successor_loop_history_latest.json",
        "loop_delta_path": workspace_root / "artifacts" / "successor_loop_delta_latest.json",
        "loop_governance_path": workspace_root / "artifacts" / "successor_loop_governance_latest.json",
        "loop_recommendation_path": workspace_root / "artifacts" / "successor_loop_recommendation_latest.json",
        "loop_follow_on_plan_path": workspace_root / "artifacts" / "successor_loop_follow_on_plan_latest.json",
        "docs_readiness_review_path": workspace_root / "docs" / "successor_docs_readiness_review.md",
        "artifact_index_consistency_path": workspace_root / "artifacts" / "successor_artifact_index_consistency_latest.json",
        "handoff_completeness_note_path": workspace_root / "docs" / "successor_handoff_completeness_note.md",
        "implementation_note_path": workspace_root / "docs" / "successor_shell_iteration_notes.md",
        "continuation_gap_plan_path": workspace_root / "plans" / "successor_continuation_gap_analysis.md",
        "readiness_note_path": workspace_root / "docs" / "successor_package_readiness_note.md",
        "promotion_bundle_note_path": workspace_root / "docs" / "successor_promotion_bundle_note.md",
        "implementation_package_root": workspace_root / "src" / "successor_shell",
        "implementation_init_path": workspace_root / "src" / "successor_shell" / "__init__.py",
        "implementation_module_path": workspace_root / "src" / "successor_shell" / "workspace_contract.py",
        "readiness_module_path": workspace_root / "src" / "successor_shell" / "successor_manifest.py",
        "implementation_test_path": workspace_root / "tests" / "test_workspace_contract.py",
        "readiness_test_path": workspace_root / "tests" / "test_successor_manifest.py",
        "readiness_summary_path": workspace_root / "artifacts" / "successor_readiness_evaluation_latest.json",
        "delivery_manifest_path": workspace_root / "artifacts" / "successor_delivery_manifest_latest.json",
        "promotion_bundle_manifest_path": workspace_root / "artifacts" / "successor_candidate_promotion_bundle_latest.json",
    }


def _sync_baseline_admission_decision_to_latest_artifacts(
    *,
    workspace_root: Path,
    paths: dict[str, Path],
    admission_review: dict[str, Any],
    admission_recommendation: dict[str, Any],
    decision_payload: dict[str, Any],
    remediation_proposal: dict[str, Any],
) -> None:
    def _apply_to_controller(payload: dict[str, Any]) -> dict[str, Any]:
        updated = dict(payload)
        updated["generated_at"] = _now()
        updated["latest_successor_baseline_admission_review_path"] = str(
            paths["baseline_admission_review_path"]
        )
        updated["latest_successor_baseline_admission_recommendation_path"] = str(
            paths["baseline_admission_recommendation_path"]
        )
        updated["latest_successor_baseline_admission_decision_path"] = str(
            paths["baseline_admission_decision_path"]
        )
        updated["latest_successor_baseline_remediation_proposal_path"] = str(
            paths["baseline_remediation_proposal_path"]
        )
        updated["baseline_admission_review_state"] = str(
            admission_review.get("admission_review_state", "")
        )
        updated["baseline_admission_recommendation_state"] = str(
            admission_recommendation.get("admission_recommendation_state", "")
        )
        updated["baseline_admission_decision_state"] = str(
            decision_payload.get("admission_decision_state", "")
        )
        updated["baseline_candidate_admitted"] = bool(
            decision_payload.get("admitted_bounded_baseline_candidate", False)
        )
        updated["baseline_remediation_objective_id"] = str(
            remediation_proposal.get("objective_id", "")
        )
        updated["successor_baseline_admission_review"] = dict(admission_review)
        updated["successor_baseline_admission_recommendation"] = dict(
            admission_recommendation
        )
        updated["successor_baseline_admission_decision"] = dict(decision_payload)
        updated["successor_baseline_remediation_proposal"] = dict(remediation_proposal)
        return updated

    controller_summary = load_controller_summary(workspace_root)
    if controller_summary:
        controller_path = controller_artifact_path(workspace_root)
        controller_path.write_text(
            _dump(_apply_to_controller(controller_summary)),
            encoding="utf-8",
        )

    session_summary = load_session_summary(workspace_root)
    if session_summary:
        updated_session = dict(session_summary)
        updated_session["generated_at"] = _now()
        current_controller = dict(updated_session.get("governed_execution_controller", {}))
        if current_controller or controller_summary:
            updated_session["governed_execution_controller"] = _apply_to_controller(
                current_controller or controller_summary
            )
        updated_session["successor_baseline_admission_review"] = dict(admission_review)
        updated_session["successor_baseline_admission_recommendation"] = dict(
            admission_recommendation
        )
        updated_session["successor_baseline_admission_decision"] = dict(decision_payload)
        updated_session["successor_baseline_remediation_proposal"] = dict(
            remediation_proposal
        )
        session_artifact_path(workspace_root).write_text(
            _dump(updated_session),
            encoding="utf-8",
        )


def _existing_relative_paths(workspace_root: Path, relative_paths: list[str]) -> list[str]:
    return [
        relative_path
        for relative_path in relative_paths
        if relative_path and (workspace_root / Path(relative_path)).exists()
    ]


def _absolute_workspace_candidate_path(workspace_root: Path, value: str) -> Path:
    candidate = Path(str(value))
    if candidate.is_absolute():
        return candidate
    return workspace_root / candidate


def _derive_candidate_comparison_remediation(
    *,
    comparison_pack: dict[str, Any],
    directive_id: str,
    workspace_root: Path,
    candidate_bundle_objective_id: str,
    completed_objective_id: str,
    completed_objective_source_kind: str,
    admitted_candidate_recorded: bool,
    stronger_than_current_bounded_baseline: bool,
    weak_areas: list[dict[str, Any]],
    baseline_remediation_proposal: dict[str, Any],
) -> dict[str, Any]:
    if not admitted_candidate_recorded:
        if baseline_remediation_proposal:
            return {
                "proposal_source": "baseline_admission_decision",
                "proposal_state": str(
                    baseline_remediation_proposal.get("proposal_state", "")
                ).strip(),
                "remediation_required": bool(
                    baseline_remediation_proposal.get("remediation_required", False)
                ),
                "objective_id": str(
                    baseline_remediation_proposal.get("objective_id", "")
                ).strip(),
                "objective_class": str(
                    baseline_remediation_proposal.get("objective_class", "")
                ).strip(),
                "title": str(baseline_remediation_proposal.get("title", "")).strip(),
                "rationale": str(
                    baseline_remediation_proposal.get("rationale", "")
                ).strip(),
                "weak_areas": list(baseline_remediation_proposal.get("weak_areas", [])),
            }
        return {
            "proposal_source": "candidate_not_admitted",
            "proposal_state": CANDIDATE_NOT_ADMITTED_STATE,
            "remediation_required": False,
            "objective_id": "",
            "objective_class": "",
            "title": "Admission decision pending or not approved",
            "rationale": "Candidate strengthening is not derived until admission is explicitly approved or a remediation-needed decision already exists.",
            "weak_areas": weak_areas,
        }

    if stronger_than_current_bounded_baseline:
        return {
            "proposal_source": "comparison_complete",
            "proposal_state": STRONGER_THAN_CURRENT_BOUNDED_BASELINE_STATE,
            "remediation_required": False,
            "objective_id": "",
            "objective_class": "",
            "title": "No comparison remediation required",
            "rationale": "The admitted candidate is already handoff-ready and conservatively stronger than the current bounded baseline reference.",
            "weak_areas": [],
        }

    templates = _remediation_template_rows(comparison_pack)
    objective_id = ""
    for item in weak_areas:
        candidate = str(item.get("failure_objective_id", "")).strip()
        if candidate:
            objective_id = candidate
            break
    if not objective_id:
        objective_id = "improve_successor_package_readiness"
    template = dict(templates.get(objective_id, {}))
    return {
        "proposal_source": "candidate_comparison_rubric",
        "proposal_state": NOT_STRONGER_ENOUGH_YET_STATE,
        "remediation_required": True,
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "candidate_bundle_objective_id": candidate_bundle_objective_id,
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "objective_id": objective_id,
        "objective_class": _objective_class_from_objective_id(objective_id),
        "title": str(template.get("title", "")).strip()
        or _humanize_objective_id(objective_id)
        or "Strengthen admitted candidate",
        "rationale": str(template.get("rationale", "")).strip()
        or "The admitted candidate is preserved, but it is not yet strong enough to serve as the preferred future bounded reference target.",
        "weak_areas": weak_areas,
    }


def _sync_candidate_lifecycle_to_latest_artifacts(
    *,
    workspace_root: Path,
    paths: dict[str, Path],
    admitted_candidate: dict[str, Any],
    admitted_candidate_handoff: dict[str, Any],
    baseline_comparison: dict[str, Any],
    reference_target: dict[str, Any],
) -> None:
    def _apply_to_controller(payload: dict[str, Any]) -> dict[str, Any]:
        updated = dict(payload)
        updated["generated_at"] = _now()
        updated["latest_successor_admitted_candidate_path"] = str(
            paths["admitted_candidate_path"]
        )
        updated["latest_successor_admitted_candidate_handoff_path"] = str(
            paths["admitted_candidate_handoff_path"]
        )
        updated["latest_successor_baseline_comparison_path"] = str(
            paths["baseline_comparison_path"]
        )
        updated["latest_successor_reference_target_path"] = str(
            paths["reference_target_path"]
        )
        updated["admitted_candidate_state"] = str(
            admitted_candidate.get("admitted_candidate_state", "")
        )
        updated["admitted_candidate_handoff_state"] = str(
            admitted_candidate_handoff.get("handoff_state", "")
        )
        updated["admitted_candidate_handoff_ready"] = bool(
            admitted_candidate_handoff.get("handoff_ready", False)
        )
        updated["baseline_comparison_state"] = str(
            baseline_comparison.get("comparison_state", "")
        )
        updated["baseline_comparison_result_state"] = str(
            baseline_comparison.get("comparison_result_state", "")
        )
        updated["stronger_than_current_bounded_baseline"] = bool(
            baseline_comparison.get("stronger_than_current_bounded_baseline", False)
        )
        updated["future_reference_target_state"] = str(
            reference_target.get("reference_target_state", "")
        )
        updated["future_reference_target_eligible"] = bool(
            reference_target.get("eligible_as_future_reference_target", False)
        )
        updated["future_reference_target_id"] = str(
            reference_target.get("preferred_reference_target_id", "")
        )
        updated["comparison_remediation_objective_id"] = str(
            dict(baseline_comparison.get("remediation_proposal", {})).get(
                "objective_id", ""
            )
        )
        updated["successor_admitted_candidate"] = dict(admitted_candidate)
        updated["successor_admitted_candidate_handoff"] = dict(
            admitted_candidate_handoff
        )
        updated["successor_baseline_comparison"] = dict(baseline_comparison)
        updated["successor_reference_target"] = dict(reference_target)
        return updated

    controller_summary = load_controller_summary(workspace_root)
    if controller_summary:
        controller_artifact_path(workspace_root).write_text(
            _dump(_apply_to_controller(controller_summary)),
            encoding="utf-8",
        )

    session_summary = load_session_summary(workspace_root)
    if session_summary:
        updated_session = dict(session_summary)
        updated_session["generated_at"] = _now()
        current_controller = dict(updated_session.get("governed_execution_controller", {}))
        if current_controller or controller_summary:
            updated_session["governed_execution_controller"] = _apply_to_controller(
                current_controller or controller_summary
            )
        updated_session["successor_admitted_candidate"] = dict(admitted_candidate)
        updated_session["successor_admitted_candidate_handoff"] = dict(
            admitted_candidate_handoff
        )
        updated_session["successor_baseline_comparison"] = dict(baseline_comparison)
        updated_session["successor_reference_target"] = dict(reference_target)
        session_artifact_path(workspace_root).write_text(
            _dump(updated_session),
            encoding="utf-8",
        )


def _sync_post_admission_quality_follow_on_to_latest_artifacts(
    *,
    workspace_root: Path,
    paths: dict[str, Path],
    reference_target_consumption: dict[str, Any],
    quality_roadmap_outputs: dict[str, Any],
    next_objective_proposal: dict[str, Any],
    reseed_outputs: dict[str, Any],
) -> None:
    composite_evaluation = dict(quality_roadmap_outputs.get("composite_evaluation", {}))
    priority_matrix = dict(quality_roadmap_outputs.get("priority_matrix", {}))
    next_pack_plan = dict(quality_roadmap_outputs.get("next_pack_plan", {}))

    def _apply_to_controller(payload: dict[str, Any]) -> dict[str, Any]:
        updated = dict(payload)
        updated["generated_at"] = _now()
        updated["latest_successor_reference_target_consumption_path"] = str(
            paths["reference_target_consumption_path"]
        )
        updated["latest_successor_quality_roadmap_path"] = str(
            paths["quality_roadmap_path"]
        )
        updated["latest_successor_quality_priority_matrix_path"] = str(
            paths["quality_priority_matrix_path"]
        )
        updated["latest_successor_quality_composite_evaluation_path"] = str(
            paths["quality_composite_evaluation_path"]
        )
        updated["latest_successor_quality_next_pack_plan_path"] = str(
            paths["quality_next_pack_plan_path"]
        )
        updated["reference_target_consumption_state"] = str(
            reference_target_consumption.get("consumption_state", "")
        )
        updated["active_bounded_reference_target_id"] = str(
            reference_target_consumption.get("active_bounded_reference_target_id", "")
        )
        updated["active_bounded_reference_target_source_kind"] = str(
            reference_target_consumption.get(
                "active_bounded_reference_target_source_kind", ""
            )
        )
        updated["active_bounded_reference_target_title"] = str(
            reference_target_consumption.get("active_bounded_reference_target_title", "")
        )
        updated["active_bounded_reference_target_path"] = str(
            reference_target_consumption.get("active_bounded_reference_target_path", "")
        )
        updated["reference_target_comparison_basis"] = str(
            reference_target_consumption.get("comparison_basis", "")
        )
        updated["reference_target_fallback_reason"] = str(
            reference_target_consumption.get("fallback_reason", "")
        )
        updated["quality_composite_state"] = str(
            composite_evaluation.get("composite_quality_state", "")
        )
        updated["materially_stronger_than_reference_target_in_aggregate"] = bool(
            composite_evaluation.get(
                "materially_stronger_than_reference_target_in_aggregate", False
            )
        )
        updated["quality_weakest_dimension_id"] = str(
            priority_matrix.get("weakest_dimension_id", "")
        )
        updated["quality_weakest_dimension_title"] = str(
            priority_matrix.get("weakest_dimension_title", "")
        )
        updated["quality_next_pack_id"] = str(
            next_pack_plan.get("selected_skill_pack_id", "")
        )
        updated["quality_next_objective_id"] = str(
            next_pack_plan.get("selected_objective_id", "")
        )
        updated["quality_next_dimension_id"] = str(
            next_pack_plan.get("selected_dimension_id", "")
        )
        updated["successor_reference_target_consumption"] = dict(
            reference_target_consumption
        )
        updated["successor_quality_roadmap"] = dict(
            quality_roadmap_outputs.get("roadmap", {})
        )
        updated["successor_quality_priority_matrix"] = dict(priority_matrix)
        updated["successor_quality_composite_evaluation"] = dict(
            composite_evaluation
        )
        updated["successor_quality_next_pack_plan"] = dict(next_pack_plan)
        if next_objective_proposal:
            updated["latest_successor_next_objective_proposal_path"] = str(
                paths["next_objective_proposal_path"]
            )
            updated["next_objective_state"] = str(
                next_objective_proposal.get("proposal_state", "")
            )
            updated["next_objective_id"] = str(
                next_objective_proposal.get("objective_id", "")
            )
            updated["next_objective_class"] = str(
                next_objective_proposal.get("objective_class", "")
            )
        if reseed_outputs:
            request_payload = dict(reseed_outputs.get("request", {}))
            effective_payload = dict(reseed_outputs.get("effective_next_objective", {}))
            updated["latest_successor_reseed_request_path"] = str(
                reseed_outputs.get("reseed_request_path", "")
            )
            updated["latest_successor_reseed_decision_path"] = str(
                reseed_outputs.get("reseed_decision_path", "")
            )
            updated["latest_successor_continuation_lineage_path"] = str(
                reseed_outputs.get("continuation_lineage_path", "")
            )
            updated["latest_successor_effective_next_objective_path"] = str(
                reseed_outputs.get("effective_next_objective_path", "")
            )
            updated["reseed_state"] = str(
                effective_payload.get(
                    "reseed_state",
                    request_payload.get("reseed_state", ""),
                )
            )
            updated["continuation_authorized"] = bool(
                effective_payload.get("continuation_authorized", False)
            )
            updated["effective_next_objective_id"] = str(
                effective_payload.get("objective_id", "")
            )
            updated["effective_next_objective_authorization_origin"] = str(
                effective_payload.get("authorization_origin", "")
            )
        return updated

    controller_summary = load_controller_summary(workspace_root)
    if controller_summary:
        controller_artifact_path(workspace_root).write_text(
            _dump(_apply_to_controller(controller_summary)),
            encoding="utf-8",
        )

    session_summary = load_session_summary(workspace_root)
    if session_summary:
        updated_session = dict(session_summary)
        updated_session["generated_at"] = _now()
        current_controller = dict(updated_session.get("governed_execution_controller", {}))
        if current_controller or controller_summary:
            updated_session["governed_execution_controller"] = _apply_to_controller(
                current_controller or controller_summary
            )
        updated_session["successor_reference_target_consumption"] = dict(
            reference_target_consumption
        )
        updated_session["successor_quality_roadmap"] = dict(
            quality_roadmap_outputs.get("roadmap", {})
        )
        updated_session["successor_quality_priority_matrix"] = dict(priority_matrix)
        updated_session["successor_quality_composite_evaluation"] = dict(
            composite_evaluation
        )
        updated_session["successor_quality_next_pack_plan"] = dict(next_pack_plan)
        if next_objective_proposal:
            updated_session["successor_next_objective_proposal"] = dict(
                next_objective_proposal
            )
        session_artifact_path(workspace_root).write_text(
            _dump(updated_session),
            encoding="utf-8",
        )


def _sync_generation_progress_to_latest_artifacts(
    *,
    workspace_root: Path,
    paths: dict[str, Path],
    generation_history: dict[str, Any],
    generation_delta: dict[str, Any],
    progress_governance: dict[str, Any],
    progress_recommendation: dict[str, Any],
) -> None:
    def _apply_to_controller(payload: dict[str, Any]) -> dict[str, Any]:
        updated = dict(payload)
        updated["generated_at"] = _now()
        updated["latest_successor_generation_history_path"] = str(
            paths["generation_history_path"]
        )
        updated["latest_successor_generation_delta_path"] = str(
            paths["generation_delta_path"]
        )
        updated["latest_successor_progress_governance_path"] = str(
            paths["progress_governance_path"]
        )
        updated["latest_successor_progress_recommendation_path"] = str(
            paths["progress_recommendation_path"]
        )
        updated["generation_index"] = int(
            generation_history.get("current_generation_index", 0) or 0
        )
        updated["prior_generation_index"] = int(
            generation_delta.get("prior_generation_index", 0) or 0
        )
        updated["generation_current_candidate_id"] = str(
            generation_delta.get("current_admitted_candidate_id", "")
        )
        updated["generation_prior_candidate_id"] = str(
            generation_delta.get("prior_admitted_candidate_id", "")
        )
        updated["generation_progress_state"] = str(
            progress_governance.get("progress_state", "")
        )
        updated["generation_progress_recommendation_state"] = str(
            progress_recommendation.get("recommendation_state", "")
        )
        updated["generation_additional_improvement_justified"] = bool(
            progress_governance.get("additional_bounded_improvement_justified", False)
        )
        updated["generation_remediation_objective_id"] = str(
            progress_recommendation.get("recommended_objective_id", "")
        )
        updated["successor_generation_history"] = dict(generation_history)
        updated["successor_generation_delta"] = dict(generation_delta)
        updated["successor_progress_governance"] = dict(progress_governance)
        updated["successor_progress_recommendation"] = dict(progress_recommendation)
        return updated

    controller_summary = load_controller_summary(workspace_root)
    if controller_summary:
        controller_artifact_path(workspace_root).write_text(
            _dump(_apply_to_controller(controller_summary)),
            encoding="utf-8",
        )

    session_summary = load_session_summary(workspace_root)
    if session_summary:
        updated_session = dict(session_summary)
        updated_session["generated_at"] = _now()
        current_controller = dict(updated_session.get("governed_execution_controller", {}))
        if current_controller or controller_summary:
            updated_session["governed_execution_controller"] = _apply_to_controller(
                current_controller or controller_summary
            )
        updated_session["successor_generation_history"] = dict(generation_history)
        updated_session["successor_generation_delta"] = dict(generation_delta)
        updated_session["successor_progress_governance"] = dict(progress_governance)
        updated_session["successor_progress_recommendation"] = dict(
            progress_recommendation
        )
        session_artifact_path(workspace_root).write_text(
            _dump(updated_session),
            encoding="utf-8",
        )


def _sync_strategy_selection_to_latest_artifacts(
    *,
    workspace_root: Path,
    paths: dict[str, Path],
    strategy_selection: dict[str, Any],
    strategy_rationale: dict[str, Any],
    strategy_follow_on_plan: dict[str, Any],
    strategy_decision_support: dict[str, Any],
) -> None:
    def _apply_to_controller(payload: dict[str, Any]) -> dict[str, Any]:
        updated = dict(payload)
        updated["generated_at"] = _now()
        updated["latest_successor_strategy_selection_path"] = str(
            paths["strategy_selection_path"]
        )
        updated["latest_successor_strategy_rationale_path"] = str(
            paths["strategy_rationale_path"]
        )
        updated["latest_successor_strategy_follow_on_plan_path"] = str(
            paths["strategy_follow_on_plan_path"]
        )
        updated["latest_successor_strategy_decision_support_path"] = str(
            paths["strategy_decision_support_path"]
        )
        updated["strategy_selection_state"] = str(
            strategy_selection.get("selected_strategy_state", "")
        )
        updated["strategy_follow_on_family"] = str(
            strategy_follow_on_plan.get("follow_on_family", "")
        )
        updated["strategy_operator_review_recommended"] = bool(
            strategy_follow_on_plan.get(
                "operator_review_recommended_before_execution",
                strategy_selection.get("operator_review_recommended", False),
            )
        )
        updated["strategy_selected_objective_id"] = str(
            strategy_follow_on_plan.get("recommended_objective_id", "")
        )
        updated["strategy_selected_objective_class"] = str(
            strategy_follow_on_plan.get("recommended_objective_class", "")
        )
        updated["strategy_selected_skill_pack_id"] = str(
            strategy_follow_on_plan.get("recommended_skill_pack_id", "")
        )
        updated["strategy_selected_dimension_id"] = str(
            strategy_follow_on_plan.get("recommended_dimension_id", "")
        )
        updated["strategy_rationale_summary"] = str(
            strategy_rationale.get("selected_strategy_rationale", "")
        )
        updated["successor_strategy_selection"] = dict(strategy_selection)
        updated["successor_strategy_rationale"] = dict(strategy_rationale)
        updated["successor_strategy_follow_on_plan"] = dict(
            strategy_follow_on_plan
        )
        updated["successor_strategy_decision_support"] = dict(
            strategy_decision_support
        )
        return updated

    controller_summary = load_controller_summary(workspace_root)
    if controller_summary:
        controller_artifact_path(workspace_root).write_text(
            _dump(_apply_to_controller(controller_summary)),
            encoding="utf-8",
        )

    session_summary = load_session_summary(workspace_root)
    if session_summary:
        updated_session = dict(session_summary)
        updated_session["generated_at"] = _now()
        current_controller = dict(updated_session.get("governed_execution_controller", {}))
        if current_controller or controller_summary:
            updated_session["governed_execution_controller"] = _apply_to_controller(
                current_controller or controller_summary
            )
        updated_session["successor_strategy_selection"] = dict(strategy_selection)
        updated_session["successor_strategy_rationale"] = dict(strategy_rationale)
        updated_session["successor_strategy_follow_on_plan"] = dict(
            strategy_follow_on_plan
        )
        updated_session["successor_strategy_decision_support"] = dict(
            strategy_decision_support
        )
        session_artifact_path(workspace_root).write_text(
            _dump(updated_session),
            encoding="utf-8",
        )


def _sync_campaign_governance_to_latest_artifacts(
    *,
    workspace_root: Path,
    paths: dict[str, Path],
    campaign_history: dict[str, Any],
    campaign_delta: dict[str, Any],
    campaign_governance: dict[str, Any],
    campaign_recommendation: dict[str, Any],
    campaign_wave_plan: dict[str, Any],
) -> None:
    def _apply_to_controller(payload: dict[str, Any]) -> dict[str, Any]:
        updated = dict(payload)
        updated["generated_at"] = _now()
        updated["latest_successor_campaign_history_path"] = str(
            paths["campaign_history_path"]
        )
        updated["latest_successor_campaign_delta_path"] = str(
            paths["campaign_delta_path"]
        )
        updated["latest_successor_campaign_governance_path"] = str(
            paths["campaign_governance_path"]
        )
        updated["latest_successor_campaign_recommendation_path"] = str(
            paths["campaign_recommendation_path"]
        )
        updated["latest_successor_campaign_wave_plan_path"] = str(
            paths["campaign_wave_plan_path"]
        )
        updated["campaign_id"] = str(
            campaign_history.get("current_campaign_id", "")
        ).strip()
        updated["campaign_wave_count"] = int(
            campaign_history.get("current_campaign_wave_count", 0) or 0
        )
        updated["campaign_progress_state"] = str(
            campaign_governance.get("campaign_progress_state", "")
        ).strip()
        updated["campaign_state"] = str(
            campaign_governance.get("campaign_state", "")
        ).strip()
        updated["campaign_recommendation_state"] = str(
            campaign_recommendation.get("recommendation_state", "")
        ).strip()
        updated["campaign_follow_on_family"] = str(
            campaign_wave_plan.get("recommended_follow_on_family", "")
        ).strip()
        updated["campaign_refresh_revised_candidate_ready"] = bool(
            campaign_governance.get("refresh_revised_candidate_justified", False)
        )
        updated["campaign_last_wave_strategy_state"] = str(
            campaign_delta.get("last_wave_strategy_state", "")
        ).strip()
        updated["campaign_last_wave_skill_pack_id"] = str(
            campaign_delta.get("last_wave_skill_pack_id", "")
        ).strip()
        updated["campaign_accumulated_improved_dimension_ids"] = list(
            campaign_governance.get("accumulated_improved_dimension_ids", [])
        )
        updated["campaign_remaining_weak_dimension_ids"] = list(
            campaign_governance.get("remaining_weak_dimension_ids", [])
        )
        updated["successor_campaign_history"] = dict(campaign_history)
        updated["successor_campaign_delta"] = dict(campaign_delta)
        updated["successor_campaign_governance"] = dict(campaign_governance)
        updated["successor_campaign_recommendation"] = dict(
            campaign_recommendation
        )
        updated["successor_campaign_wave_plan"] = dict(campaign_wave_plan)
        return updated

    controller_summary = load_controller_summary(workspace_root)
    if controller_summary:
        controller_artifact_path(workspace_root).write_text(
            _dump(_apply_to_controller(controller_summary)),
            encoding="utf-8",
        )

    session_summary = load_session_summary(workspace_root)
    if session_summary:
        updated_session = dict(session_summary)
        updated_session["generated_at"] = _now()
        current_controller = dict(
            updated_session.get("governed_execution_controller", {})
        )
        if current_controller or controller_summary:
            updated_session["governed_execution_controller"] = _apply_to_controller(
                current_controller or controller_summary
            )
        updated_session["successor_campaign_history"] = dict(campaign_history)
        updated_session["successor_campaign_delta"] = dict(campaign_delta)
        updated_session["successor_campaign_governance"] = dict(
            campaign_governance
        )
        updated_session["successor_campaign_recommendation"] = dict(
            campaign_recommendation
        )
        updated_session["successor_campaign_wave_plan"] = dict(campaign_wave_plan)
        session_artifact_path(workspace_root).write_text(
            _dump(updated_session),
            encoding="utf-8",
        )


def _sync_campaign_cycle_governance_to_latest_artifacts(
    *,
    workspace_root: Path,
    paths: dict[str, Path],
    campaign_cycle_history: dict[str, Any],
    campaign_cycle_delta: dict[str, Any],
    campaign_cycle_governance: dict[str, Any],
    campaign_cycle_recommendation: dict[str, Any],
    campaign_cycle_follow_on_plan: dict[str, Any],
) -> None:
    def _apply_to_controller(payload: dict[str, Any]) -> dict[str, Any]:
        updated = dict(payload)
        updated["generated_at"] = _now()
        updated["latest_successor_campaign_cycle_history_path"] = str(
            paths["campaign_cycle_history_path"]
        )
        updated["latest_successor_campaign_cycle_delta_path"] = str(
            paths["campaign_cycle_delta_path"]
        )
        updated["latest_successor_campaign_cycle_governance_path"] = str(
            paths["campaign_cycle_governance_path"]
        )
        updated["latest_successor_campaign_cycle_recommendation_path"] = str(
            paths["campaign_cycle_recommendation_path"]
        )
        updated["latest_successor_campaign_cycle_follow_on_plan_path"] = str(
            paths["campaign_cycle_follow_on_plan_path"]
        )
        updated["campaign_cycle_id"] = str(
            campaign_cycle_history.get("current_campaign_cycle_id", "")
        ).strip()
        updated["campaign_cycle_index"] = int(
            campaign_cycle_history.get("current_campaign_cycle_index", 0) or 0
        )
        updated["prior_campaign_cycle_index"] = int(
            campaign_cycle_delta.get("prior_campaign_cycle_index", 0) or 0
        )
        updated["campaign_cycle_progress_state"] = str(
            campaign_cycle_governance.get("campaign_cycle_progress_state", "")
        ).strip()
        updated["campaign_cycle_state"] = str(
            campaign_cycle_governance.get("campaign_cycle_state", "")
        ).strip()
        updated["campaign_cycle_recommendation_state"] = str(
            campaign_cycle_recommendation.get("recommendation_state", "")
        ).strip()
        updated["campaign_cycle_follow_on_family"] = str(
            campaign_cycle_follow_on_plan.get("recommended_follow_on_family", "")
        ).strip()
        updated["campaign_cycle_current_reference_target_id"] = str(
            campaign_cycle_history.get("current_reference_target_id", "")
        ).strip()
        updated["campaign_cycle_prior_reference_target_id"] = str(
            campaign_cycle_delta.get("prior_reference_target_id", "")
        ).strip()
        updated["campaign_cycle_source_campaign_id"] = str(
            campaign_cycle_delta.get("source_campaign_id", "")
        ).strip()
        updated["campaign_cycle_new_dimension_ids"] = list(
            campaign_cycle_delta.get("new_dimension_ids_vs_prior_cycle", [])
        )
        updated["campaign_cycle_remaining_weak_dimension_ids"] = list(
            campaign_cycle_governance.get("remaining_weak_dimension_ids", [])
        )
        updated["successor_campaign_cycle_history"] = dict(campaign_cycle_history)
        updated["successor_campaign_cycle_delta"] = dict(campaign_cycle_delta)
        updated["successor_campaign_cycle_governance"] = dict(
            campaign_cycle_governance
        )
        updated["successor_campaign_cycle_recommendation"] = dict(
            campaign_cycle_recommendation
        )
        updated["successor_campaign_cycle_follow_on_plan"] = dict(
            campaign_cycle_follow_on_plan
        )
        return updated

    controller_summary = load_controller_summary(workspace_root)
    if controller_summary:
        controller_artifact_path(workspace_root).write_text(
            _dump(_apply_to_controller(controller_summary)),
            encoding="utf-8",
        )

    session_summary = load_session_summary(workspace_root)
    if session_summary:
        updated_session = dict(session_summary)
        updated_session["generated_at"] = _now()
        current_controller = dict(
            updated_session.get("governed_execution_controller", {})
        )
        if current_controller or controller_summary:
            updated_session["governed_execution_controller"] = _apply_to_controller(
                current_controller or controller_summary
            )
        updated_session["successor_campaign_cycle_history"] = dict(
            campaign_cycle_history
        )
        updated_session["successor_campaign_cycle_delta"] = dict(
            campaign_cycle_delta
        )
        updated_session["successor_campaign_cycle_governance"] = dict(
            campaign_cycle_governance
        )
        updated_session["successor_campaign_cycle_recommendation"] = dict(
            campaign_cycle_recommendation
        )
        updated_session["successor_campaign_cycle_follow_on_plan"] = dict(
            campaign_cycle_follow_on_plan
        )
        session_artifact_path(workspace_root).write_text(
            _dump(updated_session),
            encoding="utf-8",
        )


def _sync_loop_governance_to_latest_artifacts(
    *,
    workspace_root: Path,
    paths: dict[str, Path],
    loop_history: dict[str, Any],
    loop_delta: dict[str, Any],
    loop_governance: dict[str, Any],
    loop_recommendation: dict[str, Any],
    loop_follow_on_plan: dict[str, Any],
) -> None:
    def _apply_to_controller(payload: dict[str, Any]) -> dict[str, Any]:
        updated = dict(payload)
        updated["generated_at"] = _now()
        updated["latest_successor_loop_history_path"] = str(paths["loop_history_path"])
        updated["latest_successor_loop_delta_path"] = str(paths["loop_delta_path"])
        updated["latest_successor_loop_governance_path"] = str(
            paths["loop_governance_path"]
        )
        updated["latest_successor_loop_recommendation_path"] = str(
            paths["loop_recommendation_path"]
        )
        updated["latest_successor_loop_follow_on_plan_path"] = str(
            paths["loop_follow_on_plan_path"]
        )
        updated["loop_id"] = str(loop_history.get("current_loop_id", "")).strip()
        updated["loop_index"] = int(loop_history.get("current_loop_index", 0) or 0)
        updated["prior_loop_index"] = int(
            loop_delta.get("prior_loop_index", 0) or 0
        )
        updated["loop_progress_state"] = str(
            loop_governance.get("loop_progress_state", "")
        ).strip()
        updated["loop_state"] = str(loop_governance.get("loop_state", "")).strip()
        updated["loop_recommendation_state"] = str(
            loop_recommendation.get("recommendation_state", "")
        ).strip()
        updated["loop_follow_on_family"] = str(
            loop_follow_on_plan.get("recommended_follow_on_family", "")
        ).strip()
        updated["loop_current_reference_target_id"] = str(
            loop_history.get("current_reference_target_id", "")
        ).strip()
        updated["loop_prior_reference_target_id"] = str(
            loop_delta.get("prior_reference_target_id", "")
        ).strip()
        updated["loop_source_campaign_cycle_id"] = str(
            loop_delta.get("source_campaign_cycle_id", "")
        ).strip()
        updated["loop_new_dimension_ids"] = list(
            loop_delta.get("new_dimension_ids_vs_prior_loop", [])
        )
        updated["loop_remaining_weak_dimension_ids"] = list(
            loop_governance.get("remaining_weak_dimension_ids", [])
        )
        updated["successor_loop_history"] = dict(loop_history)
        updated["successor_loop_delta"] = dict(loop_delta)
        updated["successor_loop_governance"] = dict(loop_governance)
        updated["successor_loop_recommendation"] = dict(loop_recommendation)
        updated["successor_loop_follow_on_plan"] = dict(loop_follow_on_plan)
        return updated

    controller_summary = load_controller_summary(workspace_root)
    if controller_summary:
        controller_artifact_path(workspace_root).write_text(
            _dump(_apply_to_controller(controller_summary)),
            encoding="utf-8",
        )

    session_summary = load_session_summary(workspace_root)
    if session_summary:
        updated_session = dict(session_summary)
        updated_session["generated_at"] = _now()
        current_controller = dict(
            updated_session.get("governed_execution_controller", {})
        )
        if current_controller or controller_summary:
            updated_session["governed_execution_controller"] = _apply_to_controller(
                current_controller or controller_summary
            )
        updated_session["successor_loop_history"] = dict(loop_history)
        updated_session["successor_loop_delta"] = dict(loop_delta)
        updated_session["successor_loop_governance"] = dict(loop_governance)
        updated_session["successor_loop_recommendation"] = dict(loop_recommendation)
        updated_session["successor_loop_follow_on_plan"] = dict(loop_follow_on_plan)
        session_artifact_path(workspace_root).write_text(
            _dump(updated_session),
            encoding="utf-8",
        )


def _candidate_bundle_identity_from_payload(candidate_bundle: dict[str, Any]) -> str:
    return (
        str(candidate_bundle.get("candidate_bundle_identity", "")).strip()
        or str(candidate_bundle.get("objective_id", "")).strip()
        or "successor_candidate_promotion_bundle"
    )


def _next_revised_candidate_revision_index(workspace_root: Path) -> int:
    revised_bundle = load_json(_workspace_paths(workspace_root)["revised_candidate_bundle_path"])
    current_index = int(revised_bundle.get("revision_index", 0) or 0)
    if current_index < 0:
        current_index = 0
    return current_index + 1


def _load_active_candidate_bundle_context(*, workspace_root: Path) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    base_bundle = load_json(paths["promotion_bundle_manifest_path"])
    revised_bundle = load_json(paths["revised_candidate_bundle_path"])
    revised_handoff = load_json(paths["revised_candidate_handoff_path"])
    revised_comparison = load_json(paths["revised_candidate_comparison_path"])
    revised_promotion_summary = load_json(paths["revised_candidate_promotion_summary_path"])
    reference_target = load_json(paths["reference_target_path"])
    current_reference_target_id = str(
        reference_target.get("preferred_reference_target_id", "")
    ).strip()
    revised_prior_target_id = str(
        revised_bundle.get("prior_admitted_candidate_id", "")
    ).strip()
    revised_state = str(revised_bundle.get("revised_candidate_state", "")).strip()
    if (
        revised_bundle
        and revised_prior_target_id
        and current_reference_target_id
        and revised_prior_target_id == current_reference_target_id
        and revised_state != REVISED_CANDIDATE_ADMITTED_STATE
    ):
        return {
            "variant": "revised_candidate",
            "bundle_payload": revised_bundle,
            "bundle_path": str(paths["revised_candidate_bundle_path"]),
            "handoff_payload": revised_handoff,
            "handoff_path": str(paths["revised_candidate_handoff_path"]),
            "comparison_payload": revised_comparison,
            "comparison_path": str(paths["revised_candidate_comparison_path"]),
            "promotion_summary_payload": revised_promotion_summary,
            "promotion_summary_path": str(paths["revised_candidate_promotion_summary_path"]),
            "candidate_bundle_identity": _candidate_bundle_identity_from_payload(
                revised_bundle
            ),
            "prior_admitted_candidate_id": revised_prior_target_id,
        }
    return {
        "variant": "candidate_promotion_bundle",
        "bundle_payload": base_bundle,
        "bundle_path": str(paths["promotion_bundle_manifest_path"]),
        "handoff_payload": {},
        "handoff_path": "",
        "comparison_payload": {},
        "comparison_path": "",
        "promotion_summary_payload": {},
        "promotion_summary_path": "",
        "candidate_bundle_identity": _candidate_bundle_identity_from_payload(
            base_bundle
        ),
        "prior_admitted_candidate_id": "",
    }


def _evaluate_revised_candidate_refresh_eligibility(
    *,
    workspace_root: Path,
    current_objective: dict[str, Any],
    completion_evaluation: dict[str, Any],
    reference_target_context: dict[str, Any],
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    composite_evaluation = load_json(paths["quality_composite_evaluation_path"])
    next_pack_plan = load_json(paths["quality_next_pack_plan_path"])
    readiness_summary = load_json(paths["readiness_summary_path"])
    delivery_manifest = load_json(paths["delivery_manifest_path"])
    admitted_candidate = load_json(paths["admitted_candidate_path"])
    latest_skill_pack_result = load_json(paths["skill_pack_result_path"])
    latest_quality_improvement_summary = load_json(paths["quality_improvement_summary_path"])
    active_reference_target_origin = str(
        reference_target_context.get("active_bounded_reference_target_origin", "")
    ).strip() or str(
        load_json(paths["reference_target_consumption_path"]).get(
            "active_bounded_reference_target_origin",
            "",
        )
    ).strip()
    prior_admitted_candidate_id = str(
        admitted_candidate.get("admitted_candidate_id", "")
    ).strip() or str(
        reference_target_context.get("active_bounded_reference_target_id", "")
    ).strip()
    improved_dimension_ids = _unique_string_list(
        list(composite_evaluation.get("improved_dimension_ids", []))
    )
    weak_dimension_ids = _unique_string_list(
        list(composite_evaluation.get("weak_dimension_ids", []))
    )
    materially_stronger_in_aggregate = bool(
        composite_evaluation.get(
            "materially_stronger_than_reference_target_in_aggregate",
            False,
        )
    )
    readiness_complete = bool(readiness_summary.get("completion_ready", False))
    delivery_complete = bool(delivery_manifest.get("completion_ready", False))
    latest_skill_pack_complete = str(
        latest_skill_pack_result.get("result_state", "")
    ).strip() == "complete"
    latest_quality_improvement_complete = str(
        latest_quality_improvement_summary.get("improvement_state", "")
    ).strip() == "complete"
    outputs_within_workspace = bool(
        latest_skill_pack_result.get("outputs_within_workspace", True)
    )
    objective_source_kind = str(current_objective.get("source_kind", "")).strip()
    eligible = all(
        [
            objective_source_kind in {
                OBJECTIVE_SOURCE_APPROVED_RESEED,
                OBJECTIVE_SOURCE_DIRECTIVE,
            },
            bool(completion_evaluation.get("completed", False)),
            str(reference_target_context.get("consumption_state", "")).strip()
            == REFERENCE_TARGET_CONSUMED_STATE,
            active_reference_target_origin == "admitted_candidate",
            bool(prior_admitted_candidate_id),
            materially_stronger_in_aggregate,
            bool(improved_dimension_ids),
            readiness_complete,
            delivery_complete,
            latest_skill_pack_complete,
            latest_quality_improvement_complete,
            outputs_within_workspace,
        ]
    )
    rationale = (
        "The successor now records materially stronger aggregate quality relative to the "
        "currently admitted bounded reference target, so it is eligible to be repackaged "
        "as a refreshed candidate for explicit promotion and admission review."
        if eligible
        else (
            "The successor is not yet eligible for refreshed candidate packaging because "
            "it does not yet record a complete, materially stronger aggregate improvement "
            "relative to the currently admitted bounded reference target."
        )
    )
    revision_index = _next_revised_candidate_revision_index(workspace_root)
    return {
        "eligible": eligible,
        "rationale": rationale,
        "revision_index": revision_index,
        "candidate_bundle_identity": f"prepare_candidate_promotion_bundle::revision_{revision_index:03d}",
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "active_reference_target_id": str(
            reference_target_context.get("active_bounded_reference_target_id", "")
        ).strip(),
        "active_reference_target_path": str(
            reference_target_context.get("active_bounded_reference_target_path", "")
        ).strip(),
        "quality_composite_state": str(
            composite_evaluation.get("composite_quality_state", "")
        ).strip(),
        "materially_stronger_in_aggregate": materially_stronger_in_aggregate,
        "improved_dimension_ids": improved_dimension_ids,
        "weak_dimension_ids": weak_dimension_ids,
        "next_quality_objective_id": str(
            next_pack_plan.get("selected_objective_id", "")
        ).strip(),
        "next_quality_pack_id": str(
            next_pack_plan.get("selected_skill_pack_id", "")
        ).strip(),
        "readiness_complete": readiness_complete,
        "delivery_complete": delivery_complete,
    }


def _sync_revised_candidate_outputs_to_latest_artifacts(
    *,
    workspace_root: Path,
    paths: dict[str, Path],
    revised_candidate_bundle: dict[str, Any],
    revised_candidate_handoff: dict[str, Any],
    revised_candidate_comparison: dict[str, Any],
    revised_candidate_promotion_summary: dict[str, Any],
) -> None:
    def _apply_to_controller(payload: dict[str, Any]) -> dict[str, Any]:
        updated = dict(payload)
        updated["generated_at"] = _now()
        updated["latest_successor_revised_candidate_bundle_path"] = str(
            paths["revised_candidate_bundle_path"]
        )
        updated["latest_successor_revised_candidate_handoff_path"] = str(
            paths["revised_candidate_handoff_path"]
        )
        updated["latest_successor_revised_candidate_comparison_path"] = str(
            paths["revised_candidate_comparison_path"]
        )
        updated["latest_successor_revised_candidate_promotion_summary_path"] = str(
            paths["revised_candidate_promotion_summary_path"]
        )
        updated["revised_candidate_state"] = str(
            revised_candidate_bundle.get("revised_candidate_state", "")
        )
        updated["revised_candidate_id"] = str(
            revised_candidate_bundle.get("revised_candidate_id", "")
        )
        updated["revised_candidate_prior_admitted_candidate_id"] = str(
            revised_candidate_bundle.get("prior_admitted_candidate_id", "")
        )
        updated["revised_candidate_materially_stronger_in_aggregate"] = bool(
            revised_candidate_comparison.get(
                "materially_stronger_than_prior_admitted_candidate_in_aggregate",
                False,
            )
        )
        updated["revised_candidate_reference_rollover_state"] = str(
            revised_candidate_promotion_summary.get("reference_target_rollover_state", "")
        )
        updated["successor_revised_candidate_bundle"] = dict(revised_candidate_bundle)
        updated["successor_revised_candidate_handoff"] = dict(revised_candidate_handoff)
        updated["successor_revised_candidate_comparison"] = dict(
            revised_candidate_comparison
        )
        updated["successor_revised_candidate_promotion_summary"] = dict(
            revised_candidate_promotion_summary
        )
        return updated

    controller_summary = load_controller_summary(workspace_root)
    if controller_summary:
        controller_artifact_path(workspace_root).write_text(
            _dump(_apply_to_controller(controller_summary)),
            encoding="utf-8",
        )

    session_summary = load_session_summary(workspace_root)
    if session_summary:
        updated_session = dict(session_summary)
        updated_session["generated_at"] = _now()
        current_controller = dict(updated_session.get("governed_execution_controller", {}))
        if current_controller or controller_summary:
            updated_session["governed_execution_controller"] = _apply_to_controller(
                current_controller or controller_summary
            )
        updated_session["successor_revised_candidate_bundle"] = dict(
            revised_candidate_bundle
        )
        updated_session["successor_revised_candidate_handoff"] = dict(
            revised_candidate_handoff
        )
        updated_session["successor_revised_candidate_comparison"] = dict(
            revised_candidate_comparison
        )
        updated_session["successor_revised_candidate_promotion_summary"] = dict(
            revised_candidate_promotion_summary
        )
        session_artifact_path(workspace_root).write_text(
            _dump(updated_session),
            encoding="utf-8",
        )


def _update_revised_candidate_decision_artifacts(
    *,
    workspace_root: Path,
    paths: dict[str, Path],
    decision_payload: dict[str, Any],
    admitted_candidate_payload: dict[str, Any],
    reference_target_payload: dict[str, Any],
) -> dict[str, Any]:
    revised_candidate_bundle = load_json(paths["revised_candidate_bundle_path"])
    if not revised_candidate_bundle:
        return {}
    revised_candidate_handoff = load_json(paths["revised_candidate_handoff_path"])
    revised_candidate_comparison = load_json(paths["revised_candidate_comparison_path"])
    revised_candidate_promotion_summary = load_json(
        paths["revised_candidate_promotion_summary_path"]
    )
    decision_key = str(decision_payload.get("operator_decision", "")).strip().lower()
    revised_state = {
        "approve": REVISED_CANDIDATE_ADMITTED_STATE,
        "defer": REVISED_CANDIDATE_DEFERRED_STATE,
        "reject": REVISED_CANDIDATE_REMEDIATION_REQUIRED_STATE,
    }.get(
        decision_key,
        str(revised_candidate_bundle.get("revised_candidate_state", "")).strip()
        or REVISED_CANDIDATE_RECORDED_STATE,
    )
    rollover_state = (
        "rolled_forward_to_revised_candidate"
        if decision_key == "approve"
        and bool(admitted_candidate_payload.get("admitted_candidate_recorded", False))
        else ""
    )
    rolled_forward_reference_target_id = str(
        reference_target_payload.get("preferred_reference_target_id", "")
    ).strip()
    for payload in (
        revised_candidate_bundle,
        revised_candidate_handoff,
        revised_candidate_comparison,
        revised_candidate_promotion_summary,
    ):
        if not payload:
            continue
        payload["generated_at"] = _now()
        payload["revised_candidate_state"] = revised_state
        payload["latest_admission_decision_state"] = str(
            decision_payload.get("admission_decision_state", "")
        )
        payload["latest_admission_decision_path"] = str(
            paths["baseline_admission_decision_path"]
        )
        payload["reference_target_rollover_state"] = rollover_state
        if rollover_state:
            payload["rolled_forward_reference_target_id"] = (
                rolled_forward_reference_target_id
            )
    paths["revised_candidate_bundle_path"].write_text(
        _dump(revised_candidate_bundle),
        encoding="utf-8",
    )
    paths["revised_candidate_handoff_path"].write_text(
        _dump(revised_candidate_handoff),
        encoding="utf-8",
    )
    paths["revised_candidate_comparison_path"].write_text(
        _dump(revised_candidate_comparison),
        encoding="utf-8",
    )
    paths["revised_candidate_promotion_summary_path"].write_text(
        _dump(revised_candidate_promotion_summary),
        encoding="utf-8",
    )
    _sync_revised_candidate_outputs_to_latest_artifacts(
        workspace_root=workspace_root,
        paths=paths,
        revised_candidate_bundle=revised_candidate_bundle,
        revised_candidate_handoff=revised_candidate_handoff,
        revised_candidate_comparison=revised_candidate_comparison,
        revised_candidate_promotion_summary=revised_candidate_promotion_summary,
    )
    return {
        "revised_candidate_bundle": revised_candidate_bundle,
        "revised_candidate_handoff": revised_candidate_handoff,
        "revised_candidate_comparison": revised_candidate_comparison,
        "revised_candidate_promotion_summary": revised_candidate_promotion_summary,
        "revised_candidate_bundle_path": str(paths["revised_candidate_bundle_path"]),
        "revised_candidate_handoff_path": str(paths["revised_candidate_handoff_path"]),
        "revised_candidate_comparison_path": str(paths["revised_candidate_comparison_path"]),
        "revised_candidate_promotion_summary_path": str(
            paths["revised_candidate_promotion_summary_path"]
        ),
    }


def _materialize_revised_candidate_bundle_outputs(
    *,
    workspace_root: Path,
    current_objective: dict[str, Any],
    current_promotion_bundle_payload: dict[str, Any],
    reference_target_context: dict[str, Any],
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
) -> dict[str, Any]:
    eligibility = _evaluate_revised_candidate_refresh_eligibility(
        workspace_root=workspace_root,
        current_objective=current_objective,
        completion_evaluation={"completed": True},
        reference_target_context=reference_target_context,
    )
    if not bool(eligibility.get("eligible", False)):
        return {}

    paths = _workspace_paths(workspace_root)
    roadmap = load_json(paths["quality_roadmap_path"])
    priority_matrix = load_json(paths["quality_priority_matrix_path"])
    composite_evaluation = load_json(paths["quality_composite_evaluation_path"])
    next_pack_plan = load_json(paths["quality_next_pack_plan_path"])
    latest_skill_pack_result = load_json(paths["skill_pack_result_path"])
    latest_quality_improvement_summary = load_json(
        paths["quality_improvement_summary_path"]
    )
    latest_quality_gap_summary = load_json(paths["quality_gap_summary_path"])
    review_summary = load_json(paths["review_summary_path"])
    promotion_recommendation = load_json(paths["promotion_recommendation_path"])
    continuation_lineage = load_json(paths["continuation_lineage_path"])
    readiness_summary = load_json(paths["readiness_summary_path"])
    delivery_manifest = load_json(paths["delivery_manifest_path"])
    admitted_candidate = load_json(paths["admitted_candidate_path"])

    revision_index = int(eligibility.get("revision_index", 1) or 1)
    candidate_bundle_identity = str(
        eligibility.get("candidate_bundle_identity", "")
    ).strip() or f"prepare_candidate_promotion_bundle::revision_{revision_index:03d}"
    revised_candidate_id = f"{workspace_root.name}::{candidate_bundle_identity}::revised_candidate"
    prior_admitted_candidate_id = str(
        eligibility.get("prior_admitted_candidate_id", "")
    ).strip()
    improved_dimension_ids = list(eligibility.get("improved_dimension_ids", []))
    weak_dimension_ids = list(eligibility.get("weak_dimension_ids", []))
    improved_state_paths = _unique_string_list(
        [
            str(paths["promotion_bundle_manifest_path"]),
            str(paths["promotion_bundle_note_path"]),
            str(paths["quality_roadmap_path"]),
            str(paths["quality_priority_matrix_path"]),
            str(paths["quality_composite_evaluation_path"]),
            str(paths["quality_next_pack_plan_path"]),
            str(paths["quality_gap_summary_path"]),
            str(paths["quality_improvement_summary_path"]),
            str(paths["skill_pack_result_path"]),
            str(paths["workspace_artifact_index_path"]),
            str(paths["readiness_summary_path"]),
            str(paths["delivery_manifest_path"]),
            str(paths["review_summary_path"]),
            str(paths["promotion_recommendation_path"]),
            str(paths["continuation_lineage_path"]),
        ]
    )
    revised_bundle_payload = {
        "schema_name": SUCCESSOR_REVISED_CANDIDATE_BUNDLE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_REVISED_CANDIDATE_BUNDLE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "objective_id": str(current_objective.get("objective_id", "")).strip(),
        "objective_source_kind": str(
            current_objective.get("source_kind", "")
        ).strip(),
        "revised_candidate_id": revised_candidate_id,
        "revised_candidate_state": REVISED_CANDIDATE_RECORDED_STATE,
        "candidate_bundle_identity": candidate_bundle_identity,
        "revision_index": revision_index,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "prior_reference_target_id": str(
            eligibility.get("active_reference_target_id", "")
        ).strip(),
        "prior_reference_target_path": str(
            eligibility.get("active_reference_target_path", "")
        ).strip(),
        "source_candidate_bundle_manifest_path": str(paths["promotion_bundle_manifest_path"]),
        "source_candidate_bundle_identity": _candidate_bundle_identity_from_payload(
            current_promotion_bundle_payload
        ),
        "source_candidate_bundle_variant": str(
            current_promotion_bundle_payload.get("candidate_bundle_variant", "")
        ).strip()
        or "candidate_promotion_bundle",
        "quality_roadmap_path": str(paths["quality_roadmap_path"]),
        "quality_priority_matrix_path": str(paths["quality_priority_matrix_path"]),
        "quality_composite_evaluation_path": str(
            paths["quality_composite_evaluation_path"]
        ),
        "quality_next_pack_plan_path": str(paths["quality_next_pack_plan_path"]),
        "skill_pack_result_path": str(paths["skill_pack_result_path"]),
        "quality_improvement_summary_path": str(
            paths["quality_improvement_summary_path"]
        ),
        "quality_gap_summary_path": str(paths["quality_gap_summary_path"]),
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "continuation_lineage_path": str(paths["continuation_lineage_path"]),
        "readiness_summary_path": str(paths["readiness_summary_path"]),
        "delivery_manifest_path": str(paths["delivery_manifest_path"]),
        "workspace_artifact_index_path": str(paths["workspace_artifact_index_path"]),
        "materially_stronger_than_prior_admitted_candidate_in_aggregate": bool(
            eligibility.get("materially_stronger_in_aggregate", False)
        ),
        "quality_composite_state": str(
            eligibility.get("quality_composite_state", "")
        ).strip(),
        "completion_ready": True,
        "improved_dimension_ids": improved_dimension_ids,
        "remaining_weak_dimension_ids": weak_dimension_ids,
        "improved_state_paths": improved_state_paths,
        "bundle_items": _unique_string_list(
            list(current_promotion_bundle_payload.get("bundle_items", []))
            + improved_state_paths
            + [
                str(paths["revised_candidate_bundle_path"]),
                str(paths["revised_candidate_handoff_path"]),
                str(paths["revised_candidate_comparison_path"]),
                str(paths["revised_candidate_promotion_summary_path"]),
            ]
        ),
        "promotion_review_ready": True,
        "admission_review_required": True,
        "baseline_mutation_performed": False,
        "live_baseline_replacement_permitted": False,
        "refresh_rationale": str(eligibility.get("rationale", "")).strip(),
    }
    revised_handoff_payload = {
        "schema_name": SUCCESSOR_REVISED_CANDIDATE_HANDOFF_SCHEMA_NAME,
        "schema_version": SUCCESSOR_REVISED_CANDIDATE_HANDOFF_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "revised_candidate_id": revised_candidate_id,
        "revised_candidate_state": REVISED_CANDIDATE_RECORDED_STATE,
        "candidate_bundle_identity": candidate_bundle_identity,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "handoff_ready": True,
        "handoff_state": "revised_candidate_handoff_ready",
        "bundle_items": list(revised_bundle_payload.get("bundle_items", [])),
        "candidate_contents": {
            "promotion_bundle": [str(paths["promotion_bundle_manifest_path"])],
            "quality_evidence": improved_state_paths,
        },
        "operator_review_required": True,
        "live_baseline_replacement_permitted": False,
    }
    revised_comparison_payload = {
        "schema_name": SUCCESSOR_REVISED_CANDIDATE_COMPARISON_SCHEMA_NAME,
        "schema_version": SUCCESSOR_REVISED_CANDIDATE_COMPARISON_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "revised_candidate_id": revised_candidate_id,
        "revised_candidate_state": REVISED_CANDIDATE_RECORDED_STATE,
        "candidate_bundle_identity": candidate_bundle_identity,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "prior_reference_target_id": str(
            eligibility.get("active_reference_target_id", "")
        ).strip(),
        "comparison_state": "revised_candidate_comparison_complete",
        "comparison_result_state": QUALITY_COMPOSITE_MULTI_DIMENSION_STATE,
        "materially_stronger_than_prior_admitted_candidate_in_aggregate": bool(
            eligibility.get("materially_stronger_in_aggregate", False)
        ),
        "improved_dimension_ids": improved_dimension_ids,
        "remaining_weak_dimension_ids": weak_dimension_ids,
        "promotion_worthy": True,
        "admission_worthy": True,
        "review_inputs_used": [
            {"artifact_kind": "successor_quality_roadmap", "path": str(paths["quality_roadmap_path"])},
            {"artifact_kind": "successor_quality_priority_matrix", "path": str(paths["quality_priority_matrix_path"])},
            {"artifact_kind": "successor_quality_composite_evaluation", "path": str(paths["quality_composite_evaluation_path"])},
            {"artifact_kind": "successor_quality_next_pack_plan", "path": str(paths["quality_next_pack_plan_path"])},
            {"artifact_kind": "successor_quality_gap_summary", "path": str(paths["quality_gap_summary_path"])},
            {"artifact_kind": "successor_quality_improvement_summary", "path": str(paths["quality_improvement_summary_path"])},
            {"artifact_kind": "successor_skill_pack_result", "path": str(paths["skill_pack_result_path"])},
            {"artifact_kind": "successor_candidate_promotion_bundle", "path": str(paths["promotion_bundle_manifest_path"])},
        ],
        "comparison_rationale": (
            "The improved successor now records multi-dimension bounded improvements relative "
            "to the previously admitted candidate, so this refreshed candidate is suitable for "
            "explicit promotion and admission review."
        ),
        "remediation_required": False,
        "remediation_proposal": {},
        "live_baseline_replacement_permitted": False,
    }
    revised_promotion_summary_payload = {
        "schema_name": SUCCESSOR_REVISED_CANDIDATE_PROMOTION_SUMMARY_SCHEMA_NAME,
        "schema_version": SUCCESSOR_REVISED_CANDIDATE_PROMOTION_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "revised_candidate_id": revised_candidate_id,
        "revised_candidate_state": REVISED_CANDIDATE_RECORDED_STATE,
        "candidate_bundle_identity": candidate_bundle_identity,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "quality_composite_state": str(
            composite_evaluation.get("composite_quality_state", "")
        ).strip(),
        "materially_stronger_than_prior_admitted_candidate_in_aggregate": bool(
            eligibility.get("materially_stronger_in_aggregate", False)
        ),
        "improved_dimension_ids": improved_dimension_ids,
        "remaining_weak_dimension_ids": weak_dimension_ids,
        "latest_skill_pack_id": str(
            latest_skill_pack_result.get("selected_skill_pack_id", "")
        ).strip(),
        "latest_quality_gap_id": str(
            latest_quality_gap_summary.get("quality_gap_id", "")
        ).strip(),
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "comparison_summary_path": str(paths["revised_candidate_comparison_path"]),
        "reference_target_rollover_state": "",
        "promotion_review_ready": True,
        "admission_review_required": True,
        "summary_rationale": str(eligibility.get("rationale", "")).strip(),
    }

    for artifact_path, artifact_payload, artifact_kind in (
        (
            paths["revised_candidate_bundle_path"],
            revised_bundle_payload,
            "successor_revised_candidate_bundle_json",
        ),
        (
            paths["revised_candidate_handoff_path"],
            revised_handoff_payload,
            "successor_revised_candidate_handoff_json",
        ),
        (
            paths["revised_candidate_comparison_path"],
            revised_comparison_payload,
            "successor_revised_candidate_comparison_json",
        ),
        (
            paths["revised_candidate_promotion_summary_path"],
            revised_promotion_summary_payload,
            "successor_revised_candidate_promotion_summary_json",
        ),
    ):
        _write_json(
            artifact_path,
            artifact_payload,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id="successor_revised_candidate_bundle",
            artifact_kind=artifact_kind,
        )
    _event(
        runtime_event_log_path,
        event_type="successor_revised_candidate_bundle_materialized",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        revised_candidate_id=revised_candidate_id,
        prior_admitted_candidate_id=prior_admitted_candidate_id,
        revised_candidate_bundle_path=str(paths["revised_candidate_bundle_path"]),
        materially_stronger_in_aggregate=bool(
            eligibility.get("materially_stronger_in_aggregate", False)
        ),
    )
    _event(
        runtime_event_log_path,
        event_type="successor_revised_candidate_comparison_recorded",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        revised_candidate_id=revised_candidate_id,
        comparison_path=str(paths["revised_candidate_comparison_path"]),
        improved_dimension_ids=improved_dimension_ids,
    )
    _sync_revised_candidate_outputs_to_latest_artifacts(
        workspace_root=workspace_root,
        paths=paths,
        revised_candidate_bundle=revised_bundle_payload,
        revised_candidate_handoff=revised_handoff_payload,
        revised_candidate_comparison=revised_comparison_payload,
        revised_candidate_promotion_summary=revised_promotion_summary_payload,
    )
    return {
        "revised_candidate_bundle": revised_bundle_payload,
        "revised_candidate_handoff": revised_handoff_payload,
        "revised_candidate_comparison": revised_comparison_payload,
        "revised_candidate_promotion_summary": revised_promotion_summary_payload,
        "revised_candidate_bundle_path": str(paths["revised_candidate_bundle_path"]),
        "revised_candidate_handoff_path": str(paths["revised_candidate_handoff_path"]),
        "revised_candidate_comparison_path": str(paths["revised_candidate_comparison_path"]),
        "revised_candidate_promotion_summary_path": str(
            paths["revised_candidate_promotion_summary_path"]
        ),
    }


def _materialize_admitted_candidate_lifecycle_outputs(
    *,
    workspace_root: Path,
    admission_review: dict[str, Any],
    admission_recommendation: dict[str, Any],
    decision_payload: dict[str, Any],
    baseline_remediation_proposal: dict[str, Any],
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    session_summary = load_session_summary(workspace_root)
    candidate_context = _load_active_candidate_bundle_context(workspace_root=workspace_root)
    candidate_bundle = dict(candidate_context.get("bundle_payload", {}))
    candidate_bundle_manifest_path = str(
        candidate_context.get("bundle_path", "")
    ).strip() or str(paths["promotion_bundle_manifest_path"])
    candidate_bundle_variant = str(candidate_context.get("variant", "")).strip() or (
        "candidate_promotion_bundle"
    )
    revised_candidate_bundle_path = str(
        candidate_context.get("bundle_path", "")
    ).strip() if candidate_bundle_variant == "revised_candidate" else ""
    revised_candidate_handoff_path = str(
        candidate_context.get("handoff_path", "")
    ).strip()
    revised_candidate_comparison_path = str(
        candidate_context.get("comparison_path", "")
    ).strip()
    revised_candidate_promotion_summary_path = str(
        candidate_context.get("promotion_summary_path", "")
    ).strip()
    continuation_lineage = load_json(paths["continuation_lineage_path"])
    delivery_manifest = load_json(paths["delivery_manifest_path"])
    readiness_summary = load_json(paths["readiness_summary_path"])
    artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    comparison_pack, comparison_source = _load_internal_knowledge_pack(
        session=session_summary,
        source_id=INTERNAL_SUCCESSOR_ADMITTED_CANDIDATE_COMPARISON_SOURCE_ID,
        expected_schema_name=SUCCESSOR_ADMITTED_CANDIDATE_COMPARISON_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=SUCCESSOR_ADMITTED_CANDIDATE_COMPARISON_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    state_model = dict(comparison_pack.get("state_model", {}))
    baseline_reference = dict(comparison_pack.get("baseline_reference", {}))

    directive_id = str(admission_review.get("directive_id", "")).strip()
    candidate_bundle_objective_id = str(
        admission_review.get("candidate_bundle_objective_id", "")
    ).strip()
    candidate_bundle_identity = str(
        admission_review.get("candidate_bundle_identity", "")
    ).strip() or str(
        candidate_context.get("candidate_bundle_identity", "")
    ).strip() or candidate_bundle_objective_id or "successor_candidate_promotion_bundle"
    completed_objective_id = str(
        admission_review.get("completed_objective_id", "")
    ).strip()
    completed_objective_source_kind = str(
        admission_review.get("completed_objective_source_kind", "")
    ).strip()
    prior_admitted_candidate_id = str(
        candidate_context.get("prior_admitted_candidate_id", "")
    ).strip() or str(candidate_bundle.get("prior_admitted_candidate_id", "")).strip()
    admitted_candidate_recorded = bool(
        decision_payload.get("admitted_bounded_baseline_candidate", False)
    )
    candidate_materially_stronger = bool(
        decision_payload.get(
            "candidate_materially_stronger_than_bounded_baseline",
            admission_recommendation.get(
                "candidate_materially_stronger_than_bounded_baseline",
                admission_review.get(
                    "candidate_materially_stronger_than_bounded_baseline",
                    False,
                ),
            ),
        )
    )
    admitted_candidate_id = (
        f"{workspace_root.name}::{candidate_bundle_identity or 'candidate'}::bounded_reference_candidate"
    )

    content_groups = {
        "source_modules": [
            "src/successor_shell/workspace_contract.py",
            "src/successor_shell/successor_manifest.py",
        ],
        "tests": [
            "tests/test_workspace_contract.py",
            "tests/test_successor_manifest.py",
        ],
        "docs": [
            "docs/mutable_shell_successor_design_note.md",
            "docs/successor_package_readiness_note.md",
            "docs/successor_promotion_bundle_note.md",
        ],
        "manifests_and_readiness": [
            "artifacts/workspace_artifact_index_latest.json",
            "artifacts/successor_readiness_evaluation_latest.json",
            "artifacts/successor_delivery_manifest_latest.json",
            "artifacts/successor_candidate_promotion_bundle_latest.json",
        ],
        "review_and_admission": [
            "artifacts/successor_review_summary_latest.json",
            "artifacts/successor_promotion_recommendation_latest.json",
            "artifacts/successor_next_objective_proposal_latest.json",
            "artifacts/successor_baseline_admission_review_latest.json",
            "artifacts/successor_baseline_admission_recommendation_latest.json",
            "artifacts/successor_baseline_admission_decision_latest.json",
        ],
        "lineage": [
            "artifacts/successor_continuation_lineage_latest.json",
            "artifacts/successor_effective_next_objective_latest.json",
        ],
    }
    grouped_relative_paths = {
        key: _existing_relative_paths(workspace_root, value)
        for key, value in content_groups.items()
    }
    handoff_required_relative_paths = [
        str(item).strip()
        for item in list(comparison_pack.get("handoff_required_relative_paths", []))
        if str(item).strip()
    ]
    handoff_required_evidence = [
        _relative_path_status(workspace_root, relative_path)
        for relative_path in handoff_required_relative_paths
    ]
    missing_handoff_relative_paths = [
        str(item.get("relative_path", ""))
        for item in handoff_required_evidence
        if not bool(item.get("present", False))
    ]
    handoff_ready = admitted_candidate_recorded and not missing_handoff_relative_paths
    review_evidence_complete = all(
        path.exists()
        for path in (
            paths["review_summary_path"],
            paths["promotion_recommendation_path"],
            paths["next_objective_proposal_path"],
            paths["baseline_admission_review_path"],
            paths["baseline_admission_recommendation_path"],
            paths["baseline_admission_decision_path"],
        )
    )
    lineage_coherent = bool(continuation_lineage) and (
        str(continuation_lineage.get("completed_objective_id", "")).strip()
        == completed_objective_id
    )
    manifest_completion_ready = bool(candidate_bundle.get("completion_ready", False)) and bool(
        readiness_summary.get("completion_ready", False)
    ) and bool(delivery_manifest.get("completion_ready", False))
    candidate_asset_paths = _unique_string_list(
        [
            *[str(item) for item in list(candidate_bundle.get("bundle_items", []))],
            candidate_bundle_manifest_path,
            str(paths["review_summary_path"]),
            str(paths["promotion_recommendation_path"]),
            str(paths["next_objective_proposal_path"]),
            str(paths["baseline_admission_review_path"]),
            str(paths["baseline_admission_recommendation_path"]),
            str(paths["baseline_admission_decision_path"]),
            str(paths["admitted_candidate_path"]),
            str(paths["admitted_candidate_handoff_path"]),
            str(paths["baseline_comparison_path"]),
            str(paths["reference_target_path"]),
            revised_candidate_handoff_path,
            revised_candidate_comparison_path,
            revised_candidate_promotion_summary_path,
        ]
    )
    outputs_outside_workspace = [
        item
        for item in candidate_asset_paths
        if item
        and not _is_under_path(
            _absolute_workspace_candidate_path(workspace_root, item),
            workspace_root,
        )
    ]

    check_rows: list[dict[str, Any]] = []
    weak_areas: list[dict[str, Any]] = []
    for item in list(comparison_pack.get("comparison_checks", [])):
        row = dict(item)
        check_id = str(row.get("check_id", "")).strip()
        if not check_id:
            continue
        required_relative_paths = [
            str(path).strip()
            for path in list(row.get("required_relative_paths", []))
            if str(path).strip()
        ]
        evidence_rows = [
            _relative_path_status(workspace_root, relative_path)
            for relative_path in required_relative_paths
        ]
        missing_relative_paths = [
            str(entry.get("relative_path", ""))
            for entry in evidence_rows
            if not bool(entry.get("present", False))
        ]
        passed = True
        details: list[str] = []
        if missing_relative_paths:
            passed = False
            details.append("missing required paths: " + ", ".join(missing_relative_paths))
        if bool(row.get("requires_admitted_candidate_recorded", False)) and not admitted_candidate_recorded:
            passed = False
            details.append("candidate has not been admitted yet")
        if bool(row.get("requires_handoff_ready", False)) and not handoff_ready:
            passed = False
            details.append("admitted candidate handoff is not yet ready")
        if bool(row.get("requires_candidate_strength_signal", False)) and not candidate_materially_stronger:
            passed = False
            details.append("candidate strength signal is not yet present")
        if bool(row.get("requires_review_evidence_complete", False)) and not review_evidence_complete:
            passed = False
            details.append("review, promotion, or admission evidence is incomplete")
        if bool(row.get("requires_outputs_within_workspace", False)) and outputs_outside_workspace:
            passed = False
            details.append("candidate assets escaped the bounded active workspace")
        if bool(row.get("requires_manifest_completion_ready", False)) and not manifest_completion_ready:
            passed = False
            details.append("candidate manifests are not completion_ready")
        if bool(row.get("requires_lineage_coherence", False)) and not lineage_coherent:
            passed = False
            details.append("candidate lineage is not coherent enough for audit")
        if bool(row.get("requires_no_baseline_mutation", False)) and bool(
            decision_payload.get("baseline_mutation_performed", False)
        ):
            passed = False
            details.append("live or protected baseline mutation was recorded")
        check_row = {
            "check_id": check_id,
            "title": str(row.get("title", check_id)),
            "passed": passed,
            "required_relative_paths": required_relative_paths,
            "missing_relative_paths": missing_relative_paths,
            "details": "; ".join(details) if details else "passed",
            "failure_objective_id": str(row.get("failure_objective_id", "")).strip(),
        }
        check_rows.append(check_row)
        if not passed:
            weak_areas.append(check_row)

    comparison_complete = bool(check_rows)
    stronger_than_current_bounded_baseline = bool(
        admitted_candidate_recorded
        and comparison_complete
        and not weak_areas
        and candidate_materially_stronger
        and handoff_ready
    )
    future_reference_target_eligible = bool(
        stronger_than_current_bounded_baseline and handoff_ready
    )
    remediation_proposal = _derive_candidate_comparison_remediation(
        comparison_pack=comparison_pack,
        directive_id=directive_id,
        workspace_root=workspace_root,
        candidate_bundle_objective_id=candidate_bundle_objective_id,
        completed_objective_id=completed_objective_id,
        completed_objective_source_kind=completed_objective_source_kind,
        admitted_candidate_recorded=admitted_candidate_recorded,
        stronger_than_current_bounded_baseline=stronger_than_current_bounded_baseline,
        weak_areas=weak_areas,
        baseline_remediation_proposal=baseline_remediation_proposal,
    )
    admitted_candidate_state = (
        str(
            state_model.get(
                "admitted_candidate_recorded_state",
                ADMITTED_CANDIDATE_RECORDED_STATE,
            )
        ).strip()
        if admitted_candidate_recorded
        else CANDIDATE_NOT_ADMITTED_STATE
    )
    handoff_state = (
        str(
            state_model.get(
                "handoff_ready_state",
                ADMITTED_CANDIDATE_HANDOFF_READY_STATE,
            )
        ).strip()
        if handoff_ready
        else (HANDOFF_NOT_READY_STATE if admitted_candidate_recorded else HANDOFF_NOT_APPLICABLE_STATE)
    )
    comparison_state = (
        str(
            state_model.get(
                "comparison_complete_state",
                COMPARISON_COMPLETE_STATE,
            )
        ).strip()
        if comparison_complete
        else COMPARISON_NOT_APPLICABLE_STATE
    )
    comparison_result_state = (
        str(
            state_model.get(
                "stronger_state",
                STRONGER_THAN_CURRENT_BOUNDED_BASELINE_STATE,
            )
        ).strip()
        if stronger_than_current_bounded_baseline
        else str(
            state_model.get(
                "not_stronger_state",
                NOT_STRONGER_ENOUGH_YET_STATE,
            )
        ).strip()
    )
    reference_target_state = (
        str(
            state_model.get(
                "future_reference_eligible_state",
                ELIGIBLE_AS_FUTURE_REFERENCE_TARGET_STATE,
            )
        ).strip()
        if future_reference_target_eligible
        else (
            FUTURE_REFERENCE_TARGET_DEFERRED_STATE
            if admitted_candidate_recorded
            else FUTURE_REFERENCE_TARGET_NOT_APPLICABLE_STATE
        )
    )
    comparison_rationale = (
        (
            "The refreshed candidate preserves explicit lineage to the prior admitted bounded "
            "reference target and is handoff-ready, audit-coherent, and conservatively stronger "
            "than the previous admitted candidate under the bounded comparison rubric."
            if candidate_bundle_variant == "revised_candidate"
            else "The admitted candidate is handoff-ready, audit-coherent, and conservatively stronger than the current bounded baseline reference pack."
        )
        if future_reference_target_eligible
        else (
            (
                "The refreshed candidate is preserved, but it is not yet strong enough to supersede the prior admitted bounded reference target under the current conservative comparison rubric."
                if candidate_bundle_variant == "revised_candidate"
                else "The admitted candidate is preserved, but it is not yet strong enough to become the preferred future bounded reference target under the current conservative comparison rubric."
            )
            if admitted_candidate_recorded
            else "The candidate has not been admitted yet, so it remains unavailable as a future bounded reference target."
        )
    )
    all_relative_paths = _unique_string_list(
        [
            relative_path
            for values in grouped_relative_paths.values()
            for relative_path in values
        ]
    )
    admitted_candidate_payload = {
        "schema_name": SUCCESSOR_ADMITTED_CANDIDATE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_ADMITTED_CANDIDATE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "admitted_candidate_id": admitted_candidate_id,
        "candidate_bundle_identity": candidate_bundle_identity,
        "candidate_bundle_manifest_path": candidate_bundle_manifest_path,
        "candidate_bundle_variant": candidate_bundle_variant,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "revised_candidate_bundle_path": revised_candidate_bundle_path,
        "revised_candidate_handoff_path": revised_candidate_handoff_path,
        "revised_candidate_comparison_path": revised_candidate_comparison_path,
        "revised_candidate_promotion_summary_path": revised_candidate_promotion_summary_path,
        "admission_review_path": str(paths["baseline_admission_review_path"]),
        "admission_recommendation_path": str(paths["baseline_admission_recommendation_path"]),
        "admission_decision_path": str(paths["baseline_admission_decision_path"]),
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "continuation_lineage_path": str(paths["continuation_lineage_path"]),
        "admission_decision_state": str(decision_payload.get("admission_decision_state", "")),
        "admitted_candidate_recorded": admitted_candidate_recorded,
        "admitted_candidate_state": admitted_candidate_state,
        "supersedes_prior_admitted_candidate": bool(
            candidate_bundle_variant == "revised_candidate" and prior_admitted_candidate_id
        ),
        "handoff_ready": handoff_ready,
        "handoff_state": handoff_state,
        "comparison_state": comparison_state,
        "comparison_result_state": comparison_result_state,
        "future_reference_target_state": reference_target_state,
        "future_reference_target_eligible": future_reference_target_eligible,
        "contained_relative_paths": all_relative_paths,
        "contained_groups": grouped_relative_paths,
        "operator_review_required_for_live_baseline_replacement": True,
        "live_baseline_replacement_permitted": False,
        "baseline_mutation_performed": False,
        "explicit_non_live_baseline_replacement_note": "This artifact records an admitted bounded candidate only. It does not replace or mutate the protected/live baseline.",
    }
    handoff_payload = {
        "schema_name": SUCCESSOR_ADMITTED_CANDIDATE_HANDOFF_SCHEMA_NAME,
        "schema_version": SUCCESSOR_ADMITTED_CANDIDATE_HANDOFF_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "admitted_candidate_id": admitted_candidate_id,
        "candidate_bundle_identity": candidate_bundle_identity,
        "candidate_bundle_manifest_path": candidate_bundle_manifest_path,
        "candidate_bundle_variant": candidate_bundle_variant,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "handoff_state": handoff_state,
        "handoff_ready": handoff_ready,
        "missing_required_relative_paths": missing_handoff_relative_paths,
        "required_handoff_relative_paths": handoff_required_relative_paths,
        "candidate_contents": grouped_relative_paths,
        "review_and_admission_references": {
            "review_summary_path": str(paths["review_summary_path"]),
            "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
            "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
            "baseline_admission_review_path": str(paths["baseline_admission_review_path"]),
            "baseline_admission_recommendation_path": str(paths["baseline_admission_recommendation_path"]),
            "baseline_admission_decision_path": str(paths["baseline_admission_decision_path"]),
        },
        "lineage_references": {
            "continuation_lineage_path": str(paths["continuation_lineage_path"]),
            "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        },
        "handoff_asset_root": str(workspace_root),
        "usable_as_future_reference_target": future_reference_target_eligible,
        "live_baseline_replacement_permitted": False,
        "operator_review_required_for_live_baseline_replacement": True,
    }
    comparison_payload = {
        "schema_name": SUCCESSOR_BASELINE_COMPARISON_SCHEMA_NAME,
        "schema_version": SUCCESSOR_BASELINE_COMPARISON_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "admitted_candidate_id": admitted_candidate_id,
        "candidate_bundle_identity": candidate_bundle_identity,
        "candidate_bundle_manifest_path": candidate_bundle_manifest_path,
        "candidate_bundle_variant": candidate_bundle_variant,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "baseline_reference": baseline_reference,
        "review_inputs_used": [
            {"artifact_kind": "candidate_promotion_bundle", "path": candidate_bundle_manifest_path},
            {"artifact_kind": "admitted_candidate_handoff", "path": str(paths["admitted_candidate_handoff_path"])},
            {"artifact_kind": "successor_review_summary", "path": str(paths["review_summary_path"])},
            {"artifact_kind": "successor_promotion_recommendation", "path": str(paths["promotion_recommendation_path"])},
            {"artifact_kind": "successor_baseline_admission_review", "path": str(paths["baseline_admission_review_path"])},
            {"artifact_kind": "successor_baseline_admission_recommendation", "path": str(paths["baseline_admission_recommendation_path"])},
            {"artifact_kind": "successor_baseline_admission_decision", "path": str(paths["baseline_admission_decision_path"])},
            {"artifact_kind": "workspace_artifact_index", "path": str(paths["workspace_artifact_index_path"])},
            {"artifact_kind": "knowledge_pack", "path": str(comparison_source.get("path_hint", ""))},
            *(
                [
                    {
                        "artifact_kind": "revised_candidate_handoff",
                        "path": revised_candidate_handoff_path,
                    },
                    {
                        "artifact_kind": "revised_candidate_comparison",
                        "path": revised_candidate_comparison_path,
                    },
                    {
                        "artifact_kind": "revised_candidate_promotion_summary",
                        "path": revised_candidate_promotion_summary_path,
                    },
                ]
                if candidate_bundle_variant == "revised_candidate"
                else []
            ),
        ],
        "comparison_state": comparison_state,
        "comparison_complete": comparison_complete,
        "comparison_result_state": comparison_result_state,
        "stronger_than_current_bounded_baseline": stronger_than_current_bounded_baseline,
        "eligible_as_future_reference_target": future_reference_target_eligible,
        "candidate_materially_stronger_than_bounded_baseline": candidate_materially_stronger,
        "criteria_results": check_rows,
        "weak_areas": weak_areas,
        "remediation_proposal": remediation_proposal,
        "candidate_deliverables_present": all_relative_paths,
        "handoff_ready": handoff_ready,
        "outputs_within_active_workspace": not outputs_outside_workspace,
        "lineage_coherent": lineage_coherent,
        "manifest_completion_ready": manifest_completion_ready,
        "review_evidence_complete": review_evidence_complete,
        "knowledge_pack_source": comparison_source,
        "comparison_rationale": comparison_rationale,
        "live_baseline_replacement_permitted": False,
        "operator_review_required_for_live_baseline_replacement": True,
    }
    reference_target_payload = {
        "schema_name": SUCCESSOR_REFERENCE_TARGET_SCHEMA_NAME,
        "schema_version": SUCCESSOR_REFERENCE_TARGET_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "reference_target_state": reference_target_state,
        "admitted_candidate_id": admitted_candidate_id,
        "prior_reference_target_id": prior_admitted_candidate_id,
        "eligible_as_future_reference_target": future_reference_target_eligible,
        "preferred_reference_target_id": admitted_candidate_id if future_reference_target_eligible else str(baseline_reference.get("reference_id", "")).strip(),
        "preferred_reference_target_source_kind": "admitted_candidate" if future_reference_target_eligible else str(baseline_reference.get("reference_kind", "")).strip() or "current_bounded_reference",
        "preferred_reference_target_path": str(paths["admitted_candidate_path"]) if future_reference_target_eligible else str(comparison_source.get("path_hint", "")),
        "candidate_bundle_manifest_path": candidate_bundle_manifest_path,
        "candidate_bundle_variant": candidate_bundle_variant,
        "baseline_comparison_path": str(paths["baseline_comparison_path"]),
        "admission_decision_path": str(paths["baseline_admission_decision_path"]),
        "future_runs_should_compare_against": admitted_candidate_id if future_reference_target_eligible else str(baseline_reference.get("reference_id", "")).strip(),
        "protected_live_baseline_reference_id": str(
            baseline_reference.get("reference_id", "")
        ).strip(),
        "protected_live_baseline_source_kind": str(
            baseline_reference.get("reference_kind", "")
        ).strip()
        or "internal_bounded_reference_pack",
        "protected_live_baseline_title": str(
            baseline_reference.get("reference_title", "")
        ).strip()
        or _humanize_objective_id(
            str(baseline_reference.get("reference_id", "")).strip()
        ),
        "protected_live_baseline_path_hint": str(
            baseline_reference.get("path_hint", "")
        ).strip()
        or str(comparison_source.get("path_hint", "")),
        "reference_target_rationale": comparison_rationale,
        "reference_target_rollover_state": (
            "rolled_forward_to_revised_candidate"
            if future_reference_target_eligible
            and candidate_bundle_variant == "revised_candidate"
            and prior_admitted_candidate_id
            else ""
        ),
        "supersedes_reference_target_id": prior_admitted_candidate_id,
        "remediation_proposal": remediation_proposal,
        "live_baseline_replacement_permitted": False,
        "explicit_non_live_baseline_replacement_note": "This artifact can guide future bounded comparisons, but it does not replace the current protected/live baseline.",
    }
    return {
        "admitted_candidate": admitted_candidate_payload,
        "admitted_candidate_handoff": handoff_payload,
        "baseline_comparison": comparison_payload,
        "reference_target": reference_target_payload,
        "admitted_candidate_path": str(paths["admitted_candidate_path"]),
        "admitted_candidate_handoff_path": str(paths["admitted_candidate_handoff_path"]),
        "baseline_comparison_path": str(paths["baseline_comparison_path"]),
        "reference_target_path": str(paths["reference_target_path"]),
        "workspace_artifact_index": artifact_index,
    }


def successor_auto_continue_policy_path(root: str | Path | None) -> Path:
    base = Path(root) if root is not None else Path(
        os.environ.get(OPERATOR_POLICY_ROOT_ENV, "").strip() or Path.cwd()
    )
    return base / "successor_auto_continue_policy_latest.json"


def _objective_class_from_objective_id(objective_id: str) -> str:
    token = str(objective_id or "").strip()
    return token if token in AUTO_CONTINUE_OBJECTIVE_CLASSES else token


def _unique_string_list(items: list[Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in items:
        token = str(item or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        values.append(token)
    return values


def _split_objective_classes(value: Any) -> list[str]:
    raw = str(value or "").replace("\r", "\n").replace(",", "\n").replace(";", "\n")
    tokens = []
    seen: set[str] = set()
    for item in raw.splitlines():
        token = str(item or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def build_default_successor_auto_continue_policy() -> dict[str, Any]:
    return {
        "schema_name": SUCCESSOR_AUTO_CONTINUE_POLICY_SCHEMA_NAME,
        "schema_version": SUCCESSOR_AUTO_CONTINUE_POLICY_SCHEMA_VERSION,
        "generated_at": _now(),
        "enabled": False,
        "allowed_objective_classes": [],
        "available_objective_classes": list(AUTO_CONTINUE_OBJECTIVE_CLASSES),
        "max_auto_continue_chain_length": 1,
        "require_manual_approval_for_first_entry": True,
        "require_review_supported_proposals": True,
        "policy_scope": "approved_bounded_next_objective_classes_only",
    }


def _sanitize_successor_auto_continue_policy(payload: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(payload.get("enabled", False))
    if isinstance(payload.get("enabled"), str):
        enabled = str(payload.get("enabled", "")).strip().lower() in {"1", "true", "yes", "on", "enabled"}
    allowed_classes = [
        item
        for item in _split_objective_classes(payload.get("allowed_objective_classes", ""))
        if item in AUTO_CONTINUE_OBJECTIVE_CLASSES
    ]
    if isinstance(payload.get("allowed_objective_classes"), list):
        allowed_classes = [
            str(item).strip()
            for item in list(payload.get("allowed_objective_classes", []))
            if str(item).strip() in AUTO_CONTINUE_OBJECTIVE_CLASSES
        ]
    max_chain = int(payload.get("max_auto_continue_chain_length", 1) or 1)
    if max_chain < 1:
        max_chain = 1
    require_first_entry = bool(payload.get("require_manual_approval_for_first_entry", True))
    if isinstance(payload.get("require_manual_approval_for_first_entry"), str):
        require_first_entry = str(payload.get("require_manual_approval_for_first_entry", "")).strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
            "disabled",
        }
    require_review_supported = bool(payload.get("require_review_supported_proposals", True))
    if isinstance(payload.get("require_review_supported_proposals"), str):
        require_review_supported = str(payload.get("require_review_supported_proposals", "")).strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
            "disabled",
        }
    return {
        "schema_name": SUCCESSOR_AUTO_CONTINUE_POLICY_SCHEMA_NAME,
        "schema_version": SUCCESSOR_AUTO_CONTINUE_POLICY_SCHEMA_VERSION,
        "generated_at": _now(),
        "enabled": enabled,
        "allowed_objective_classes": allowed_classes,
        "available_objective_classes": list(AUTO_CONTINUE_OBJECTIVE_CLASSES),
        "max_auto_continue_chain_length": max_chain,
        "require_manual_approval_for_first_entry": require_first_entry,
        "require_review_supported_proposals": require_review_supported,
        "policy_scope": "approved_bounded_next_objective_classes_only",
    }


def load_successor_auto_continue_policy(root: str | Path | None) -> dict[str, Any]:
    path = successor_auto_continue_policy_path(root)
    payload = load_json(path)
    if not payload:
        return build_default_successor_auto_continue_policy()
    return _sanitize_successor_auto_continue_policy(payload)


def save_successor_auto_continue_policy(payload: dict[str, Any], *, root: str | Path | None) -> dict[str, Any]:
    cleaned = _sanitize_successor_auto_continue_policy(payload)
    path = successor_auto_continue_policy_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump(cleaned), encoding="utf-8")
    return cleaned


def load_successor_auto_continue_state(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    return load_json(_workspace_paths(Path(workspace_root))["auto_continue_state_path"])


def load_successor_auto_continue_decision(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    return load_json(_workspace_paths(Path(workspace_root))["auto_continue_decision_path"])


def _write_successor_auto_continue_state_and_decision(
    *,
    workspace_root: Path,
    operator_root: str | Path | None,
    review_summary: dict[str, Any],
    promotion_recommendation: dict[str, Any],
    next_objective_proposal: dict[str, Any],
    reseed_request_path: str,
    reseed_decision_path: str,
    continuation_lineage_path: str,
    effective_next_objective_path: str,
    continuation_authorized: bool,
    decision_reason: str,
    decision_actor: str,
    authorization_origin: str,
    operator_decision: str,
    effective_objective_id: str,
    effective_objective_title: str,
    continuation_transition_state: str = AUTO_CONTINUE_TRANSITION_NOT_STARTED,
    continuation_started_in_session: bool = False,
    transition_target_cycle_index: int = 0,
    chain_count_override: int | None = None,
    staging_decision: str = AUTO_CONTINUE_STAGING_NOT_APPLICABLE,
    staging_rationale: str = "",
    remaining_counted_cycle_budget: int = 0,
    compact_objective_eligible: bool = False,
    counts_toward_cycle_cap: bool = True,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    policy_path = successor_auto_continue_policy_path(operator_root)
    policy_payload = load_successor_auto_continue_policy(operator_root)
    prior_state = load_successor_auto_continue_state(workspace_root)
    proposed_objective_id = str(next_objective_proposal.get("objective_id", "")).strip()
    proposed_objective_class = _objective_class_from_objective_id(proposed_objective_id)
    effective_objective_class = _objective_class_from_objective_id(effective_objective_id)
    prior_manual_classes = _unique_string_list(
        list(prior_state.get("manually_approved_objective_classes", []))
    )
    current_chain_count = int(prior_state.get("current_chain_count", 0) or 0)
    if chain_count_override is not None:
        current_chain_count = int(chain_count_override)
    elif authorization_origin == AUTO_CONTINUE_ORIGIN_POLICY and continuation_authorized:
        current_chain_count += 1
    elif operator_decision in {"approve", "reject", "defer"}:
        current_chain_count = 0

    manual_classes = list(prior_manual_classes)
    if operator_decision == "approve" and proposed_objective_class:
        manual_classes = _unique_string_list(manual_classes + [proposed_objective_class])

    state_payload = {
        "schema_name": SUCCESSOR_AUTO_CONTINUE_STATE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_AUTO_CONTINUE_STATE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(review_summary.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "policy_path": str(policy_path),
        "enabled": bool(policy_payload.get("enabled", False)),
        "allowed_objective_classes": list(policy_payload.get("allowed_objective_classes", [])),
        "available_objective_classes": list(policy_payload.get("available_objective_classes", [])),
        "max_auto_continue_chain_length": int(
            policy_payload.get("max_auto_continue_chain_length", 1) or 1
        ),
        "require_manual_approval_for_first_entry": bool(
            policy_payload.get("require_manual_approval_for_first_entry", True)
        ),
        "require_review_supported_proposals": bool(
            policy_payload.get("require_review_supported_proposals", True)
        ),
        "current_chain_count": int(current_chain_count),
        "manually_approved_objective_classes": manual_classes,
        "last_decision_reason": decision_reason,
        "last_decision_actor": decision_actor,
        "last_continuation_origin": authorization_origin,
        "last_operator_decision": operator_decision,
        "last_completed_objective_id": str(review_summary.get("completed_objective_id", "")),
        "last_completed_objective_source_kind": str(
            review_summary.get("completed_objective_source_kind", "")
        ),
        "last_proposed_objective_id": proposed_objective_id,
        "last_proposed_objective_class": proposed_objective_class,
        "last_effective_objective_id": effective_objective_id,
        "last_effective_objective_class": effective_objective_class,
        "continuation_authorized": continuation_authorized,
        "auto_continue_executed": bool(continuation_started_in_session),
        "continuation_transition_state": continuation_transition_state,
        "continuation_started_in_session": bool(continuation_started_in_session),
        "transition_target_cycle_index": int(transition_target_cycle_index or 0),
        "staging_decision": str(staging_decision or AUTO_CONTINUE_STAGING_NOT_APPLICABLE),
        "staging_rationale": str(staging_rationale or "").strip(),
        "remaining_counted_cycle_budget": int(remaining_counted_cycle_budget or 0),
        "compact_objective_eligible": bool(compact_objective_eligible),
        "counts_toward_cycle_cap": bool(counts_toward_cycle_cap),
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
        "reseed_request_path": str(reseed_request_path),
        "reseed_decision_path": str(reseed_decision_path),
        "continuation_lineage_path": str(continuation_lineage_path),
        "effective_next_objective_path": str(effective_next_objective_path),
    }
    decision_payload = {
        "schema_name": SUCCESSOR_AUTO_CONTINUE_DECISION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_AUTO_CONTINUE_DECISION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(review_summary.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "policy_path": str(policy_path),
        "enabled": bool(policy_payload.get("enabled", False)),
        "allowed_objective_classes": list(policy_payload.get("allowed_objective_classes", [])),
        "max_auto_continue_chain_length": int(
            policy_payload.get("max_auto_continue_chain_length", 1) or 1
        ),
        "require_manual_approval_for_first_entry": bool(
            policy_payload.get("require_manual_approval_for_first_entry", True)
        ),
        "require_review_supported_proposals": bool(
            policy_payload.get("require_review_supported_proposals", True)
        ),
        "decision_reason": decision_reason,
        "decision_actor": decision_actor,
        "authorization_origin": authorization_origin,
        "operator_decision": operator_decision,
        "continuation_authorized": continuation_authorized,
        "current_chain_count": int(current_chain_count),
        "continuation_transition_state": continuation_transition_state,
        "continuation_started_in_session": bool(continuation_started_in_session),
        "transition_target_cycle_index": int(transition_target_cycle_index or 0),
        "staging_decision": str(staging_decision or AUTO_CONTINUE_STAGING_NOT_APPLICABLE),
        "staging_rationale": str(staging_rationale or "").strip(),
        "remaining_counted_cycle_budget": int(remaining_counted_cycle_budget or 0),
        "compact_objective_eligible": bool(compact_objective_eligible),
        "counts_toward_cycle_cap": bool(counts_toward_cycle_cap),
        "completed_objective_id": str(review_summary.get("completed_objective_id", "")),
        "completed_objective_source_kind": str(
            review_summary.get("completed_objective_source_kind", "")
        ),
        "promotion_recommendation_state": str(
            promotion_recommendation.get("promotion_recommendation_state", "")
        ),
        "review_status": str(review_summary.get("review_status", "")),
        "proposed_objective_id": proposed_objective_id,
        "proposed_objective_class": proposed_objective_class,
        "effective_objective_id": effective_objective_id,
        "effective_objective_class": effective_objective_class,
        "effective_objective_title": effective_objective_title,
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
        "reseed_request_path": str(reseed_request_path),
        "reseed_decision_path": str(reseed_decision_path),
        "continuation_lineage_path": str(continuation_lineage_path),
        "effective_next_objective_path": str(effective_next_objective_path),
    }
    paths["auto_continue_state_path"].parent.mkdir(parents=True, exist_ok=True)
    paths["auto_continue_state_path"].write_text(_dump(state_payload), encoding="utf-8")
    paths["auto_continue_decision_path"].write_text(_dump(decision_payload), encoding="utf-8")
    return {
        "state": state_payload,
        "decision": decision_payload,
        "state_path": str(paths["auto_continue_state_path"]),
        "decision_path": str(paths["auto_continue_decision_path"]),
        "policy_path": str(policy_path),
    }


def _evaluate_successor_auto_continue(
    *,
    workspace_root: Path,
    session: dict[str, Any],
    execution_profile: str,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    stop_reason: str,
    review_outputs: dict[str, Any],
    reseed_outputs: dict[str, Any],
    allow_same_session_execution: bool = False,
    preferred_staging_decision: str = AUTO_CONTINUE_STAGING_NOT_APPLICABLE,
    preferred_staging_rationale: str = "",
    remaining_counted_cycle_budget: int = 0,
    compact_objective_eligible: bool = False,
    counts_toward_cycle_cap: bool = True,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    review_summary = dict(review_outputs.get("review_summary", {}))
    promotion_recommendation = dict(review_outputs.get("promotion_recommendation", {}))
    next_objective_proposal = dict(review_outputs.get("next_objective_proposal", {}))
    operator_root = _operator_root_from_session(session)
    policy_payload = load_successor_auto_continue_policy(operator_root)
    proposed_objective_id = str(next_objective_proposal.get("objective_id", "")).strip()
    proposed_objective_class = _objective_class_from_objective_id(proposed_objective_id)
    prior_state = load_successor_auto_continue_state(workspace_root)
    prior_chain_count = int(prior_state.get("current_chain_count", 0) or 0)
    manual_classes = _unique_string_list(
        list(prior_state.get("manually_approved_objective_classes", []))
    )

    decision_reason = AUTO_CONTINUE_REASON_DISABLED
    continuation_authorized = False
    authorization_origin = ""
    continuation_transition_state = AUTO_CONTINUE_TRANSITION_NOT_STARTED
    materialized_outputs = dict(reseed_outputs)
    resolved_staging_decision = AUTO_CONTINUE_STAGING_NOT_APPLICABLE
    resolved_staging_rationale = ""

    if stop_reason != STOP_REASON_COMPLETED:
        decision_reason = AUTO_CONTINUE_REASON_REVIEW_REQUIRED
    elif not proposed_objective_id:
        decision_reason = AUTO_CONTINUE_REASON_NO_PROPOSAL
    elif not bool(policy_payload.get("enabled", False)):
        decision_reason = AUTO_CONTINUE_REASON_DISABLED
    elif execution_profile != "bounded_active_workspace_coding" or not str(workspace_root).strip():
        decision_reason = AUTO_CONTINUE_REASON_INCOMPATIBLE_POLICY
    elif bool(review_summary.get("operator_review_required", False)) and bool(
        policy_payload.get("require_review_supported_proposals", True)
    ) and not str(promotion_recommendation.get("promotion_recommendation_state", "")).strip():
        decision_reason = AUTO_CONTINUE_REASON_REVIEW_REQUIRED
    elif proposed_objective_class not in list(policy_payload.get("allowed_objective_classes", [])):
        decision_reason = AUTO_CONTINUE_REASON_NOT_WHITELISTED
    elif bool(policy_payload.get("require_manual_approval_for_first_entry", True)) and (
        proposed_objective_class not in manual_classes
    ):
        decision_reason = AUTO_CONTINUE_REASON_REVIEW_REQUIRED
    elif prior_chain_count >= int(policy_payload.get("max_auto_continue_chain_length", 1) or 1):
        decision_reason = AUTO_CONTINUE_REASON_MAX_CHAIN_REACHED
    else:
        materialized_outputs = materialize_successor_reseed_decision(
            workspace_root=workspace_root,
            operator_decision="auto_continue",
            actor="successor_auto_continue_policy",
            operator_root=operator_root,
        )
        decision_reason = (
            AUTO_CONTINUE_REASON_EXECUTED
            if bool(allow_same_session_execution)
            else AUTO_CONTINUE_REASON_AUTHORIZED
        )
        continuation_authorized = True
        authorization_origin = AUTO_CONTINUE_ORIGIN_POLICY
        continuation_transition_state = (
            AUTO_CONTINUE_TRANSITION_STARTED
            if bool(allow_same_session_execution)
            else AUTO_CONTINUE_TRANSITION_NOT_STARTED
        )

    if continuation_authorized:
        resolved_staging_decision = str(
            preferred_staging_decision or AUTO_CONTINUE_STAGING_NOT_APPLICABLE
        )
        resolved_staging_rationale = str(preferred_staging_rationale or "").strip()
    elif str(preferred_staging_decision or "").strip() not in {
        "",
        AUTO_CONTINUE_STAGING_NOT_APPLICABLE,
    }:
        resolved_staging_decision = str(preferred_staging_decision).strip()
        resolved_staging_rationale = str(preferred_staging_rationale or "").strip()
    elif proposed_objective_id and decision_reason == AUTO_CONTINUE_REASON_REVIEW_REQUIRED:
        resolved_staging_decision = AUTO_CONTINUE_STAGING_REVIEW_GATE
        resolved_staging_rationale = (
            "operator review remains required before the proposed next objective "
            f"{proposed_objective_id} can continue inside the current governed session"
        )

    state_outputs = _write_successor_auto_continue_state_and_decision(
        workspace_root=workspace_root,
        operator_root=operator_root,
        review_summary=review_summary,
        promotion_recommendation=promotion_recommendation,
        next_objective_proposal=next_objective_proposal,
        reseed_request_path=str(materialized_outputs.get("reseed_request_path", "")),
        reseed_decision_path=str(materialized_outputs.get("reseed_decision_path", "")),
        continuation_lineage_path=str(materialized_outputs.get("continuation_lineage_path", "")),
        effective_next_objective_path=str(
            materialized_outputs.get("effective_next_objective_path", "")
        ),
        continuation_authorized=continuation_authorized,
        decision_reason=decision_reason,
        decision_actor="successor_auto_continue_policy",
        authorization_origin=authorization_origin,
        operator_decision="auto_continue" if continuation_authorized else "no_auto_continue",
        effective_objective_id=str(
            dict(materialized_outputs.get("effective_next_objective", {})).get("objective_id", "")
        ).strip(),
        effective_objective_title=str(
            dict(materialized_outputs.get("effective_next_objective", {})).get("title", "")
        ).strip(),
        continuation_transition_state=continuation_transition_state,
        continuation_started_in_session=bool(
            continuation_authorized and allow_same_session_execution
        ),
        staging_decision=resolved_staging_decision,
        staging_rationale=resolved_staging_rationale,
        remaining_counted_cycle_budget=int(remaining_counted_cycle_budget or 0),
        compact_objective_eligible=bool(compact_objective_eligible),
        counts_toward_cycle_cap=bool(counts_toward_cycle_cap),
    )

    if str(runtime_event_log_path):
        _event(
            runtime_event_log_path,
            event_type="successor_auto_continue_evaluated",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root.name),
            workspace_root=str(workspace_root),
            auto_continue_reason=decision_reason,
            proposed_objective_id=proposed_objective_id,
            objective_class=proposed_objective_class,
            continuation_authorized=continuation_authorized,
            authorization_origin=authorization_origin,
            auto_continue_chain_count=int(
                dict(state_outputs.get("state", {})).get("current_chain_count", 0) or 0
            ),
            max_auto_continue_chain_length=int(
                policy_payload.get("max_auto_continue_chain_length", 1) or 1
            ),
            staging_decision=resolved_staging_decision,
            staging_rationale=resolved_staging_rationale,
            remaining_counted_cycle_budget=int(remaining_counted_cycle_budget or 0),
            compact_objective_eligible=bool(compact_objective_eligible),
            counts_toward_cycle_cap=bool(counts_toward_cycle_cap),
            auto_continue_policy_path=str(state_outputs.get("policy_path", "")),
            auto_continue_state_path=str(state_outputs.get("state_path", "")),
            auto_continue_decision_path=str(state_outputs.get("decision_path", "")),
        )
    return {
        "reason": decision_reason,
        "continuation_authorized": continuation_authorized,
        "authorization_origin": authorization_origin,
        "transition_state": continuation_transition_state,
        "reseed_outputs": materialized_outputs,
        "policy": policy_payload,
        "state": dict(state_outputs.get("state", {})),
        "decision": dict(state_outputs.get("decision", {})),
        "policy_path": str(state_outputs.get("policy_path", "")),
        "state_path": str(state_outputs.get("state_path", "")),
        "decision_path": str(state_outputs.get("decision_path", "")),
        "staging_decision": resolved_staging_decision,
        "staging_rationale": resolved_staging_rationale,
        "remaining_counted_cycle_budget": int(remaining_counted_cycle_budget or 0),
        "compact_objective_eligible": bool(compact_objective_eligible),
        "counts_toward_cycle_cap": bool(counts_toward_cycle_cap),
    }


def _start_same_session_auto_continue(
    *,
    workspace_root: Path,
    current_objective: dict[str, Any],
    review_outputs: dict[str, Any],
    reseed_outputs: dict[str, Any],
    auto_continue_outputs: dict[str, Any],
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    completed_cycle_index: int,
    next_cycle_index: int | None = None,
    staging_decision: str = AUTO_CONTINUE_STAGING_NEXT_CYCLE,
    staging_rationale: str = "",
    remaining_counted_cycle_budget: int = 0,
    compact_objective_eligible: bool = False,
    counts_toward_cycle_cap: bool = True,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    next_cycle_index = int(next_cycle_index or (int(completed_cycle_index) + 1))
    review_summary = dict(review_outputs.get("review_summary", {}))
    promotion_recommendation = dict(review_outputs.get("promotion_recommendation", {}))
    next_objective_proposal = dict(review_outputs.get("next_objective_proposal", {}))
    effective_next_objective = load_json(paths["effective_next_objective_path"])
    auto_continue_state = load_json(paths["auto_continue_state_path"])
    auto_continue_decision = load_json(paths["auto_continue_decision_path"])
    continuation_lineage = load_json(paths["continuation_lineage_path"])

    effective_next_objective["generated_at"] = _now()
    effective_next_objective["execution_state"] = "same_session_execution_started"
    effective_next_objective["same_session_cycle_started"] = True
    effective_next_objective["same_session_start_cycle_index"] = int(next_cycle_index)
    effective_next_objective["staging_decision"] = str(
        staging_decision or AUTO_CONTINUE_STAGING_NEXT_CYCLE
    )
    effective_next_objective["staging_rationale"] = str(staging_rationale or "").strip()
    effective_next_objective["remaining_counted_cycle_budget"] = int(
        remaining_counted_cycle_budget or 0
    )
    effective_next_objective["compact_objective_eligible"] = bool(compact_objective_eligible)
    effective_next_objective["counts_toward_cycle_cap"] = bool(counts_toward_cycle_cap)
    effective_next_objective["prior_completed_objective_id"] = str(
        current_objective.get("objective_id", "")
    ).strip()
    effective_next_objective["prior_completed_objective_source_kind"] = str(
        current_objective.get("source_kind", "")
    ).strip()
    paths["effective_next_objective_path"].write_text(
        _dump(effective_next_objective),
        encoding="utf-8",
    )

    current_chain_count = int(
        dict(auto_continue_outputs.get("state", {})).get("current_chain_count", 0) or 0
    )
    if auto_continue_state:
        auto_continue_state["generated_at"] = _now()
        auto_continue_state["last_decision_reason"] = AUTO_CONTINUE_REASON_EXECUTED
        auto_continue_state["last_continuation_origin"] = AUTO_CONTINUE_ORIGIN_POLICY
        auto_continue_state["continuation_authorized"] = True
        auto_continue_state["auto_continue_executed"] = True
        auto_continue_state["continuation_transition_state"] = AUTO_CONTINUE_TRANSITION_STARTED
        auto_continue_state["continuation_started_in_session"] = True
        auto_continue_state["transition_target_cycle_index"] = int(next_cycle_index)
        auto_continue_state["current_chain_count"] = int(current_chain_count)
        auto_continue_state["staging_decision"] = str(
            staging_decision or AUTO_CONTINUE_STAGING_NEXT_CYCLE
        )
        auto_continue_state["staging_rationale"] = str(staging_rationale or "").strip()
        auto_continue_state["remaining_counted_cycle_budget"] = int(
            remaining_counted_cycle_budget or 0
        )
        auto_continue_state["compact_objective_eligible"] = bool(compact_objective_eligible)
        auto_continue_state["counts_toward_cycle_cap"] = bool(counts_toward_cycle_cap)
        auto_continue_state["last_completed_objective_id"] = str(
            current_objective.get("objective_id", "")
        ).strip()
        auto_continue_state["last_completed_objective_source_kind"] = str(
            current_objective.get("source_kind", "")
        ).strip()
        auto_continue_state["last_effective_objective_id"] = str(
            effective_next_objective.get("objective_id", "")
        ).strip()
        auto_continue_state["last_effective_objective_class"] = str(
            effective_next_objective.get("objective_class", "")
        ).strip()
        paths["auto_continue_state_path"].write_text(_dump(auto_continue_state), encoding="utf-8")

    if auto_continue_decision:
        auto_continue_decision["generated_at"] = _now()
        auto_continue_decision["decision_reason"] = AUTO_CONTINUE_REASON_EXECUTED
        auto_continue_decision["authorization_origin"] = AUTO_CONTINUE_ORIGIN_POLICY
        auto_continue_decision["continuation_authorized"] = True
        auto_continue_decision["continuation_transition_state"] = AUTO_CONTINUE_TRANSITION_STARTED
        auto_continue_decision["continuation_started_in_session"] = True
        auto_continue_decision["transition_target_cycle_index"] = int(next_cycle_index)
        auto_continue_decision["current_chain_count"] = int(current_chain_count)
        auto_continue_decision["staging_decision"] = str(
            staging_decision or AUTO_CONTINUE_STAGING_NEXT_CYCLE
        )
        auto_continue_decision["staging_rationale"] = str(staging_rationale or "").strip()
        auto_continue_decision["remaining_counted_cycle_budget"] = int(
            remaining_counted_cycle_budget or 0
        )
        auto_continue_decision["compact_objective_eligible"] = bool(compact_objective_eligible)
        auto_continue_decision["counts_toward_cycle_cap"] = bool(counts_toward_cycle_cap)
        auto_continue_decision["completed_objective_id"] = str(
            current_objective.get("objective_id", "")
        ).strip()
        auto_continue_decision["completed_objective_source_kind"] = str(
            current_objective.get("source_kind", "")
        ).strip()
        auto_continue_decision["effective_objective_id"] = str(
            effective_next_objective.get("objective_id", "")
        ).strip()
        auto_continue_decision["effective_objective_class"] = str(
            effective_next_objective.get("objective_class", "")
        ).strip()
        auto_continue_decision["effective_objective_title"] = str(
            effective_next_objective.get("title", "")
        ).strip()
        paths["auto_continue_decision_path"].write_text(_dump(auto_continue_decision), encoding="utf-8")

    if continuation_lineage:
        continuation_lineage["generated_at"] = _now()
        continuation_lineage["completed_objective_id"] = str(
            current_objective.get("objective_id", "")
        ).strip()
        continuation_lineage["completed_objective_source_kind"] = str(
            current_objective.get("source_kind", "")
        ).strip()
        continuation_lineage["continuation_authorized"] = True
        continuation_lineage["authorization_origin"] = AUTO_CONTINUE_ORIGIN_POLICY
        continuation_lineage["effective_objective_id"] = str(
            effective_next_objective.get("objective_id", "")
        ).strip()
        continuation_lineage["effective_objective_class"] = str(
            effective_next_objective.get("objective_class", "")
        ).strip()
        continuation_lineage["effective_objective_title"] = str(
            effective_next_objective.get("title", "")
        ).strip()
        continuation_lineage["effective_objective_execution_state"] = str(
            effective_next_objective.get("execution_state", "")
        ).strip()
        continuation_lineage["continuation_transition_state"] = AUTO_CONTINUE_TRANSITION_STARTED
        continuation_lineage["continuation_started_in_session"] = True
        continuation_lineage["transition_target_cycle_index"] = int(next_cycle_index)
        continuation_lineage["staging_decision"] = str(
            staging_decision or AUTO_CONTINUE_STAGING_NEXT_CYCLE
        )
        continuation_lineage["staging_rationale"] = str(staging_rationale or "").strip()
        continuation_lineage["remaining_counted_cycle_budget"] = int(
            remaining_counted_cycle_budget or 0
        )
        continuation_lineage["compact_objective_eligible"] = bool(compact_objective_eligible)
        continuation_lineage["counts_toward_cycle_cap"] = bool(counts_toward_cycle_cap)
        paths["continuation_lineage_path"].write_text(_dump(continuation_lineage), encoding="utf-8")

    transition_path = (
        paths["cycles_root"]
        / f"cycle_{int(completed_cycle_index):03d}_auto_continue_transition.json"
    )
    transition_payload = {
        "schema_name": "GovernedExecutionSuccessorAutoContinueTransition",
        "schema_version": "governed_execution_successor_auto_continue_transition_v1",
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "completed_cycle_index": int(completed_cycle_index),
        "next_cycle_index": int(next_cycle_index),
        "transition_state": AUTO_CONTINUE_TRANSITION_STARTED,
        "completed_objective_id": str(current_objective.get("objective_id", "")).strip(),
        "completed_objective_class": str(current_objective.get("objective_class", "")).strip(),
        "completed_objective_source_kind": str(current_objective.get("source_kind", "")).strip(),
        "review_status": str(review_summary.get("review_status", "")).strip(),
        "promotion_recommendation_state": str(
            promotion_recommendation.get("promotion_recommendation_state", "")
        ).strip(),
        "proposed_objective_id": str(next_objective_proposal.get("objective_id", "")).strip(),
        "proposed_objective_class": str(
            next_objective_proposal.get("objective_class", "")
        ).strip()
        or _objective_class_from_objective_id(str(next_objective_proposal.get("objective_id", "")).strip()),
        "effective_objective_id": str(effective_next_objective.get("objective_id", "")).strip(),
        "effective_objective_class": str(
            effective_next_objective.get("objective_class", "")
        ).strip(),
        "effective_objective_title": str(effective_next_objective.get("title", "")).strip(),
        "authorization_origin": AUTO_CONTINUE_ORIGIN_POLICY,
        "continuation_authorized": True,
        "current_chain_count": int(current_chain_count),
        "staging_decision": str(staging_decision or AUTO_CONTINUE_STAGING_NEXT_CYCLE),
        "staging_rationale": str(staging_rationale or "").strip(),
        "remaining_counted_cycle_budget": int(remaining_counted_cycle_budget or 0),
        "compact_objective_eligible": bool(compact_objective_eligible),
        "counts_toward_cycle_cap": bool(counts_toward_cycle_cap),
        "review_summary_path": str(review_outputs.get("review_summary_path", "")),
        "promotion_recommendation_path": str(
            review_outputs.get("promotion_recommendation_path", "")
        ),
        "next_objective_proposal_path": str(
            review_outputs.get("next_objective_proposal_path", "")
        ),
        "reseed_request_path": str(reseed_outputs.get("reseed_request_path", "")),
        "reseed_decision_path": str(reseed_outputs.get("reseed_decision_path", "")),
        "continuation_lineage_path": str(paths["continuation_lineage_path"]),
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        "auto_continue_state_path": str(paths["auto_continue_state_path"]),
        "auto_continue_decision_path": str(paths["auto_continue_decision_path"]),
    }
    transition_path.parent.mkdir(parents=True, exist_ok=True)
    transition_path.write_text(_dump(transition_payload), encoding="utf-8")
    _event(
        runtime_event_log_path,
        event_type="successor_auto_continue_cycle_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        completed_cycle_index=int(completed_cycle_index),
        next_cycle_index=int(next_cycle_index),
        completed_objective_id=str(current_objective.get("objective_id", "")).strip(),
        effective_objective_id=str(effective_next_objective.get("objective_id", "")).strip(),
        objective_class=str(effective_next_objective.get("objective_class", "")).strip(),
        authorization_origin=AUTO_CONTINUE_ORIGIN_POLICY,
        continuation_authorized=True,
        auto_continue_reason=AUTO_CONTINUE_REASON_EXECUTED,
        auto_continue_chain_count=int(current_chain_count),
        staging_decision=str(staging_decision or AUTO_CONTINUE_STAGING_NEXT_CYCLE),
        staging_rationale=str(staging_rationale or "").strip(),
        remaining_counted_cycle_budget=int(remaining_counted_cycle_budget or 0),
        compact_objective_eligible=bool(compact_objective_eligible),
        counts_toward_cycle_cap=bool(counts_toward_cycle_cap),
        effective_next_objective_path=str(paths["effective_next_objective_path"]),
        auto_continue_state_path=str(paths["auto_continue_state_path"]),
        auto_continue_decision_path=str(paths["auto_continue_decision_path"]),
        continuation_transition_path=str(transition_path),
    )
    return {
        "transition_path": str(transition_path),
        "transition_state": AUTO_CONTINUE_TRANSITION_STARTED,
        "next_cycle_index": int(next_cycle_index),
        "effective_next_objective": effective_next_objective,
        "state": auto_continue_state,
        "decision": auto_continue_decision,
        "continuation_lineage": continuation_lineage,
    }


def _run_compact_follow_on_same_invocation(
    *,
    bootstrap_summary: dict[str, Any],
    session: dict[str, Any],
    payload: dict[str, Any],
    workspace_root: Path,
    current_directive: dict[str, Any],
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    controller_mode: str,
    completed_cycle_index: int,
    current_objective: dict[str, Any],
    review_outputs: dict[str, Any],
    reseed_outputs: dict[str, Any],
    auto_continue_outputs: dict[str, Any],
    staging_decision: str,
    staging_rationale: str,
    remaining_counted_cycle_budget: int,
    compact_objective_eligible: bool,
) -> dict[str, Any]:
    next_cycle_index = int(completed_cycle_index) + 1
    transition_outputs = _start_same_session_auto_continue(
        workspace_root=workspace_root,
        current_objective=current_objective,
        review_outputs=review_outputs,
        reseed_outputs=reseed_outputs,
        auto_continue_outputs=auto_continue_outputs,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        completed_cycle_index=int(completed_cycle_index),
        next_cycle_index=int(next_cycle_index),
        staging_decision=staging_decision,
        staging_rationale=staging_rationale,
        remaining_counted_cycle_budget=int(remaining_counted_cycle_budget or 0),
        compact_objective_eligible=bool(compact_objective_eligible),
        counts_toward_cycle_cap=False,
    )
    planning_context = _build_trusted_planning_context(
        current_directive=current_directive,
        workspace_root=workspace_root,
        session=session,
        cycle_index=int(next_cycle_index),
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        work_item_id="governed_execution_controller",
    )
    selected_stage = dict(dict(planning_context.get("next_step", {})).get("selected_stage", {}))
    _event(
        runtime_event_log_path,
        event_type="governed_execution_cycle_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(next_cycle_index),
        controller_mode=str(controller_mode),
        invocation_model=_invocation_model_for_mode(controller_mode),
        stage_id=str(selected_stage.get("stage_id", "")),
        cycle_kind=str(selected_stage.get("cycle_kind", "")),
        next_recommended_cycle=str(
            dict(planning_context.get("next_step", {})).get("next_recommended_cycle", "")
        ),
        counts_toward_cycle_cap=False,
        staged_compact_follow_on=True,
        staging_decision=staging_decision,
        staging_rationale=staging_rationale,
        remaining_counted_cycle_budget=int(remaining_counted_cycle_budget or 0),
    )
    current_payload = run_initial_bounded_workspace_work(
        bootstrap_summary=bootstrap_summary,
        session=session,
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        planning_context=planning_context,
        cycle_index=int(next_cycle_index),
    )
    latest_summary_artifact_path = (
        str(dict(current_payload.get("work_cycle", {})).get("summary_artifact_path", "")).strip()
        or str(_workspace_paths(workspace_root)["summary_path"])
    )
    latest_cycle_summary = load_json(Path(latest_summary_artifact_path))
    latest_completion_evaluation = _directive_completion_evaluation(
        current_directive=current_directive,
        workspace_root=workspace_root,
        session=session,
        latest_cycle_summary=latest_cycle_summary,
    )
    current_payload, augmented_summary, latest_cycle_summary_archive_path = _augment_cycle_payloads(
        payload=current_payload,
        workspace_root=workspace_root,
        cycle_index=int(next_cycle_index),
        controller_mode=controller_mode,
        latest_cycle_summary=latest_cycle_summary,
        completion_evaluation=latest_completion_evaluation,
    )
    cycle_status = str(current_payload.get("status", "")).strip()
    cycle_kind = str(dict(current_payload.get("work_cycle", {})).get("cycle_kind", "")).strip()
    cycle_row = {
        "cycle_index": int(next_cycle_index),
        "cycle_kind": cycle_kind,
        "status": cycle_status,
        "summary_artifact_path": latest_summary_artifact_path,
        "cycle_summary_archive_path": latest_cycle_summary_archive_path,
        "next_recommended_cycle": str(
            dict(current_payload.get("work_cycle", {})).get("next_recommended_cycle", "")
        ).strip(),
        "output_artifact_paths": list(
            dict(current_payload.get("work_cycle", {})).get("output_artifact_paths", [])
        ),
        "newly_created_paths": list(
            dict(current_payload.get("work_cycle", {})).get("newly_created_paths", [])
        ),
        "counts_toward_cycle_cap": False,
        "staged_compact_follow_on": True,
        "budget_staging_decision": staging_decision,
        "budget_staging_rationale": staging_rationale,
    }
    _event(
        runtime_event_log_path,
        event_type="directive_stop_condition_evaluated",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(next_cycle_index),
        completed=bool(latest_completion_evaluation.get("completed", False)),
        reason=str(latest_completion_evaluation.get("reason", "")),
        fallback_used=bool(latest_completion_evaluation.get("fallback_used", False)),
        counts_toward_cycle_cap=False,
        staged_compact_follow_on=True,
        staging_decision=staging_decision,
    )
    _event(
        runtime_event_log_path,
        event_type="governed_execution_cycle_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(next_cycle_index),
        cycle_kind=cycle_kind,
        status=cycle_status,
        summary_artifact_path=latest_summary_artifact_path,
        cycle_summary_archive_path=latest_cycle_summary_archive_path,
        counts_toward_cycle_cap=False,
        staged_compact_follow_on=True,
        staging_decision=staging_decision,
        staging_rationale=staging_rationale,
        remaining_counted_cycle_budget=int(remaining_counted_cycle_budget or 0),
    )
    stop_reason = ""
    stop_detail = ""
    if cycle_status == STOP_REASON_FAILURE:
        stop_reason = STOP_REASON_FAILURE
        stop_detail = str(current_payload.get("reason", "")).strip()
    elif cycle_status == STOP_REASON_NO_WORK:
        stop_reason = STOP_REASON_NO_WORK
        stop_detail = str(current_payload.get("reason", "")).strip()
    elif bool(latest_completion_evaluation.get("completed", False)):
        stop_reason = STOP_REASON_COMPLETED
        stop_detail = str(latest_completion_evaluation.get("reason", "")).strip()
    else:
        stop_reason = STOP_REASON_MAX_CAP
        stop_detail = (
            "compact follow-on objective "
            f"{str(dict(transition_outputs.get('effective_next_objective', {})).get('objective_id', '')).strip() or '<unknown>'} "
            "started in-session but still requires a fresh governed invocation to continue"
        )
    return {
        "payload": current_payload,
        "summary_artifact_path": latest_summary_artifact_path,
        "cycle_summary_archive_path": latest_cycle_summary_archive_path,
        "completion_evaluation": latest_completion_evaluation,
        "cycle_row": cycle_row,
        "transition_outputs": transition_outputs,
        "planning_context": planning_context,
        "stop_reason": stop_reason,
        "stop_detail": stop_detail,
    }


def _workspace_baseline(workspace_root: Path) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    baseline_paths = [
        paths["plan_path"],
        paths["design_path"],
        paths["file_plan_path"],
        paths["summary_path"],
        paths["src_readme_path"],
        paths["tests_readme_path"],
    ]
    planning_summary = load_json(paths["summary_path"])
    return {
        **paths,
        "baseline_artifact_paths": [str(path) for path in baseline_paths if path.exists()],
        "has_planning_baseline": all(path.exists() for path in baseline_paths),
        "planning_summary": planning_summary,
        "implementation_materialized": all(
            path.exists()
            for path in (
                paths["implementation_init_path"],
                paths["implementation_module_path"],
                paths["implementation_test_path"],
                paths["implementation_note_path"],
                paths["implementation_summary_path"],
            )
        ),
        "continuation_gap_materialized": all(
            path.exists()
            for path in (
                paths["continuation_gap_plan_path"],
                paths["trusted_planning_evidence_path"],
                paths["missing_deliverables_path"],
                paths["next_step_derivation_path"],
                paths["completion_evaluation_path"],
            )
        ),
        "readiness_materialized": all(
            path.exists()
            for path in (
                paths["readiness_module_path"],
                paths["readiness_test_path"],
                paths["readiness_note_path"],
                paths["readiness_summary_path"],
                paths["delivery_manifest_path"],
            )
        ),
        "review_materialized": all(
            path.exists()
            for path in (
                paths["review_summary_path"],
                paths["promotion_recommendation_path"],
                paths["next_objective_proposal_path"],
            )
        ),
        "reseed_materialized": all(
            path.exists()
            for path in (
                paths["reseed_request_path"],
                paths["reseed_decision_path"],
                paths["continuation_lineage_path"],
                paths["effective_next_objective_path"],
            )
        ),
        "promotion_bundle_materialized": all(
            path.exists()
            for path in (
                paths["promotion_bundle_note_path"],
                paths["promotion_bundle_manifest_path"],
            )
        ),
        "admitted_candidate_materialized": all(
            path.exists()
            for path in (
                paths["admitted_candidate_path"],
                paths["admitted_candidate_handoff_path"],
                paths["baseline_comparison_path"],
                paths["reference_target_path"],
            )
        ),
    }


def _directive_text_blob(current_directive: dict[str, Any]) -> str:
    return " ".join(
        [
            str(current_directive.get("directive_text", "")).strip(),
            str(current_directive.get("clarified_intent_summary", "")).strip(),
            *[str(item).strip() for item in list(current_directive.get("constraints", []))],
            *[str(item).strip() for item in list(current_directive.get("success_criteria", []))],
            *[str(item).strip() for item in list(current_directive.get("trusted_sources", []))],
        ]
    ).lower()


def _package_root_from_session(session: dict[str, Any]) -> Path:
    package_root = str(session.get("package_root", "")).strip()
    if package_root:
        return Path(package_root)
    return Path(__file__).resolve().parents[1]


def _operator_root_from_session(session: dict[str, Any]) -> Path:
    operator_root = str(session.get("operator_policy_root", "")).strip()
    if operator_root:
        return Path(operator_root)
    env_root = str(os.environ.get(OPERATOR_POLICY_ROOT_ENV, "")).strip()
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parents[1] / "operator_state"


def _knowledge_pack_fallback_path(package_root: Path, source_id: str) -> Path:
    knowledge_pack_root = package_root / "trusted_sources" / "knowledge_packs"
    if source_id == INTERNAL_SUCCESSOR_COMPLETION_SOURCE_ID:
        return knowledge_pack_root / "successor_completion_knowledge_pack_v1.json"
    if source_id == INTERNAL_WORKSPACE_CONTINUATION_SOURCE_ID:
        return knowledge_pack_root / "workspace_continuation_knowledge_pack_v1.json"
    if source_id == INTERNAL_SUCCESSOR_PROMOTION_REVIEW_SOURCE_ID:
        return knowledge_pack_root / "successor_promotion_review_knowledge_pack_v1.json"
    if source_id == INTERNAL_SUCCESSOR_BASELINE_ADMISSION_SOURCE_ID:
        return knowledge_pack_root / "successor_baseline_admission_knowledge_pack_v1.json"
    if source_id == INTERNAL_SUCCESSOR_ADMITTED_CANDIDATE_COMPARISON_SOURCE_ID:
        return knowledge_pack_root / "successor_admitted_candidate_comparison_knowledge_pack_v1.json"
    return knowledge_pack_root / "unknown_knowledge_pack.json"


def _skill_pack_fallback_path(package_root: Path, skill_pack_id: str) -> Path:
    skill_pack_root = package_root / "trusted_sources" / "skill_packs"
    if skill_pack_id == INTERNAL_SUCCESSOR_WORKSPACE_REVIEW_SKILL_PACK_ID:
        return skill_pack_root / "successor_workspace_review_pack_v1.json"
    if skill_pack_id == INTERNAL_SUCCESSOR_TEST_STRENGTHENING_SKILL_PACK_ID:
        return skill_pack_root / "successor_test_strengthening_pack_v1.json"
    if skill_pack_id == INTERNAL_SUCCESSOR_MANIFEST_QUALITY_SKILL_PACK_ID:
        return skill_pack_root / "successor_manifest_quality_pack_v1.json"
    if skill_pack_id == INTERNAL_SUCCESSOR_DOCS_READINESS_SKILL_PACK_ID:
        return skill_pack_root / "successor_docs_readiness_pack_v1.json"
    if skill_pack_id == INTERNAL_SUCCESSOR_ARTIFACT_INDEX_CONSISTENCY_SKILL_PACK_ID:
        return skill_pack_root / "successor_artifact_index_consistency_pack_v1.json"
    if skill_pack_id == INTERNAL_SUCCESSOR_HANDOFF_COMPLETENESS_SKILL_PACK_ID:
        return skill_pack_root / "successor_handoff_completeness_pack_v1.json"
    return skill_pack_root / "unknown_skill_pack.json"


def _session_binding_rows(session: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("source_id", "")).strip(): dict(item)
        for item in list(dict(session.get("trusted_source_bindings", {})).get("bindings", []))
        if str(item.get("source_id", "")).strip()
    }


def _session_availability_rows(session: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("source_id", "")).strip(): dict(item)
        for item in list(dict(session.get("trusted_source_availability", {})).get("sources", []))
        if str(item.get("source_id", "")).strip()
    }


def _load_internal_knowledge_pack(
    *,
    session: dict[str, Any],
    source_id: str,
    expected_schema_name: str,
    expected_schema_version: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    package_root = _package_root_from_session(session)
    bindings_by_source = _session_binding_rows(session)
    availability_by_source = _session_availability_rows(session)
    binding = dict(bindings_by_source.get(source_id, {}))
    availability = dict(availability_by_source.get(source_id, {}))
    fallback_path = _knowledge_pack_fallback_path(package_root, source_id)
    candidate_path = str(binding.get("path_hint", "")).strip()
    load_status = "missing"
    reason = "knowledge pack binding is missing from the frozen operator session"

    if candidate_path and bool(binding.get("enabled", False)) and bool(availability.get("ready_for_launch", False)):
        load_status = "loaded_from_trusted_source_binding"
        reason = str(availability.get("availability_reason", "ready")).strip() or "ready"
    elif not binding and fallback_path.exists():
        candidate_path = str(fallback_path)
        load_status = "loaded_from_packaged_fallback"
        reason = "binding missing from frozen session; packaged fallback was used conservatively"
    else:
        candidate_path = candidate_path or str(fallback_path)
        reason = str(availability.get("availability_reason", reason)).strip() or reason

    payload = load_json(Path(candidate_path)) if candidate_path else {}
    loaded = (
        str(payload.get("schema_name", "")).strip() == expected_schema_name
        and str(payload.get("schema_version", "")).strip() == expected_schema_version
    )
    if not loaded:
        if payload:
            load_status = "invalid_schema"
            reason = (
                f"expected {expected_schema_name}/{expected_schema_version} but found "
                f"{payload.get('schema_name', '<missing>')}/{payload.get('schema_version', '<missing>')}"
            )
        else:
            load_status = "missing_or_unreadable"

    return payload if loaded else {}, {
        "source_id": source_id,
        "source_kind": str(binding.get("source_kind", availability.get("source_kind", "local_bundle"))).strip()
        or "local_bundle",
        "path_hint": str(candidate_path),
        "binding_enabled": bool(binding.get("enabled", False)) if binding else False,
        "ready_for_launch": bool(availability.get("ready_for_launch", False)) if availability else bool(load_status == "loaded_from_packaged_fallback"),
        "load_status": load_status,
        "loaded": loaded,
        "reason": reason,
        "schema_name": str(payload.get("schema_name", "")) if loaded else "",
        "schema_version": str(payload.get("schema_version", "")) if loaded else "",
        "pack_id": str(payload.get("pack_id", "")) if loaded else "",
    }


def _load_internal_skill_pack_manifest(
    *,
    session: dict[str, Any],
    skill_pack_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    package_root = _package_root_from_session(session)
    candidate_path = _skill_pack_fallback_path(package_root, skill_pack_id)
    payload = load_json(candidate_path)
    loaded = (
        str(payload.get("schema_name", "")).strip()
        == SUCCESSOR_SKILL_PACK_MANIFEST_SCHEMA_NAME
        and str(payload.get("schema_version", "")).strip()
        == SUCCESSOR_SKILL_PACK_MANIFEST_SCHEMA_VERSION
        and str(payload.get("skill_pack_id", "")).strip() == skill_pack_id
    )
    return payload if loaded else {}, {
        "skill_pack_id": skill_pack_id,
        "source_kind": "local_bundle",
        "path_hint": str(candidate_path),
        "loaded": loaded,
        "load_status": (
            "loaded_from_packaged_skill_pack"
            if loaded
            else "missing_or_invalid_skill_pack_manifest"
        ),
        "reason": (
            "loaded packaged bounded skill-pack manifest"
            if loaded
            else "skill-pack manifest is missing or invalid"
        ),
        "schema_name": str(payload.get("schema_name", "")) if loaded else "",
        "schema_version": str(payload.get("schema_version", "")) if loaded else "",
        "skill_pack_version": str(payload.get("skill_pack_version", "")) if loaded else "",
        "capability_class": str(payload.get("capability_class", "")) if loaded else "",
    }


def _relative_path_status(workspace_root: Path, relative_path: str) -> dict[str, Any]:
    absolute_path = workspace_root / Path(relative_path)
    return {
        "relative_path": relative_path,
        "absolute_path": str(absolute_path),
        "present": absolute_path.exists(),
    }


def _evaluate_successor_completion(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    completion_pack: dict[str, Any],
    reference_target_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    directive_blob = _directive_text_blob(current_directive)
    deliverable_checks: list[dict[str, Any]] = []
    completed_by_id: dict[str, bool] = {}

    for deliverable in list(completion_pack.get("deliverables", [])):
        row = dict(deliverable)
        deliverable_id = str(row.get("deliverable_id", "")).strip()
        if not deliverable_id:
            continue
        required_tokens = [str(item).strip().lower() for item in list(row.get("required_when_tokens_any", [])) if str(item).strip()]
        required = bool(row.get("required", False))
        if required_tokens:
            required = any(token in directive_blob for token in required_tokens)
        evidence_rows = [
            _relative_path_status(workspace_root, str(item))
            for item in list(row.get("evidence_relative_paths", []))
            if str(item).strip()
        ]
        evidence_paths_present = [item for item in evidence_rows if bool(item.get("present", False))]
        completed = bool(not required or all(item["present"] for item in evidence_rows))
        completed_by_id[deliverable_id] = completed
        deliverable_checks.append(
            {
                "deliverable_id": deliverable_id,
                "title": str(row.get("title", deliverable_id)),
                "required": required,
                "completed": completed,
                "missing_evidence_relative_paths": [
                    str(item.get("relative_path", ""))
                    for item in evidence_rows
                    if not bool(item.get("present", False))
                ],
                "evidence_paths_present": [str(item.get("absolute_path", "")) for item in evidence_paths_present],
                "evidence_rows": evidence_rows,
            }
        )

    missing_required = [item for item in deliverable_checks if bool(item.get("required", False)) and not bool(item.get("completed", False))]
    completed = len(missing_required) == 0 and bool(deliverable_checks)
    partial_states: list[str] = []
    if completed_by_id.get("planning_bundle") and not completed_by_id.get("implementation_bundle"):
        partial_states.append("planning_bundle_only")
    if completed_by_id.get("implementation_bundle") and not completed_by_id.get("continuation_gap_analysis"):
        partial_states.append("first_implementation_bundle_only")
    if completed_by_id.get("continuation_gap_analysis") and not completed_by_id.get("successor_readiness_bundle"):
        partial_states.append("ready_for_readiness_bundle")

    reason = (
        "required bounded successor deliverables are present inside the active workspace"
        if completed
        else "bounded successor deliverables remain incomplete inside the active workspace"
    )
    return {
        "schema_name": COMPLETION_EVALUATION_SCHEMA_NAME,
        "schema_version": COMPLETION_EVALUATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "completion_pack_id": str(completion_pack.get("pack_id", "")),
        "completion_rule": str(completion_pack.get("completion_rule", SUCCESSOR_COMPLETION_RULE)),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_root": str(workspace_root),
        "completed": completed,
        "reason": reason,
        "partial_completion_states": partial_states,
        "required_deliverable_count": sum(1 for item in deliverable_checks if bool(item.get("required", False))),
        "missing_required_deliverables": [
            {
                "deliverable_id": str(item.get("deliverable_id", "")),
                "title": str(item.get("title", "")),
                "missing_evidence_relative_paths": list(item.get("missing_evidence_relative_paths", [])),
            }
            for item in missing_required
        ],
        "deliverable_checks": deliverable_checks,
        "recommended_stop": completed,
        "working_reference_target": dict(reference_target_context or {}),
        "reference_target_consumption_state": str(
            dict(reference_target_context or {}).get("consumption_state", "")
        ),
        "active_bounded_reference_target_id": str(
            dict(reference_target_context or {}).get(
                "active_bounded_reference_target_id",
                "",
            )
        ),
        "protected_live_baseline_reference_id": str(
            dict(reference_target_context or {}).get(
                "protected_live_baseline_reference_id",
                "",
            )
        ),
        "comparison_basis": str(
            dict(reference_target_context or {}).get("comparison_basis", "")
        ),
    }


def _humanize_objective_id(objective_id: str) -> str:
    token = str(objective_id or "").strip().replace("_", " ")
    return token[:1].upper() + token[1:] if token else ""


def _objective_template_rows(review_pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("objective_id", "")).strip(): dict(item)
        for item in list(review_pack.get("objective_templates", []))
        if str(item.get("objective_id", "")).strip()
    }


def _remediation_template_rows(pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("objective_id", "")).strip(): dict(item)
        for item in list(pack.get("remediation_objective_templates", []))
        if str(item.get("objective_id", "")).strip()
    }


def _collect_cycle_output_paths(cycle_rows: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in cycle_rows:
        for field_name in ("output_artifact_paths", "newly_created_paths"):
            for item in list(row.get(field_name, [])):
                candidate = str(item).strip()
                if not candidate or candidate in seen:
                    continue
                seen.add(candidate)
                ordered.append(candidate)
    return ordered


def _cycle_history_summary(cycle_rows: list[dict[str, Any]]) -> dict[str, Any]:
    cycle_kind_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    counted_cycle_count = 0
    compact_follow_on_count = 0
    for row in cycle_rows:
        cycle_kind = str(row.get("cycle_kind", "")).strip() or "unknown"
        status = str(row.get("status", "")).strip() or "unknown"
        cycle_kind_counts[cycle_kind] = cycle_kind_counts.get(cycle_kind, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1
        if bool(row.get("counts_toward_cycle_cap", True)):
            counted_cycle_count += 1
        else:
            compact_follow_on_count += 1
    return {
        "cycle_count": len(cycle_rows),
        "counted_cycle_count": counted_cycle_count,
        "compact_follow_on_count": compact_follow_on_count,
        "cycle_kind_counts": cycle_kind_counts,
        "status_counts": status_counts,
        "latest_cycle_index": int(cycle_rows[-1].get("cycle_index", 0)) if cycle_rows else 0,
        "latest_cycle_kind": str(cycle_rows[-1].get("cycle_kind", "")) if cycle_rows else "",
    }


def _counted_cycle_rows(cycle_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in cycle_rows if bool(row.get("counts_toward_cycle_cap", True))]


def _cycle_budget_overview(
    cycle_rows: list[dict[str, Any]],
    *,
    max_cycles_per_invocation: int,
) -> dict[str, int]:
    counted_rows = _counted_cycle_rows(cycle_rows)
    staged_rows = [row for row in cycle_rows if not bool(row.get("counts_toward_cycle_cap", True))]
    return {
        "counted_cycle_count": len(counted_rows),
        "staged_compact_follow_on_count": len(staged_rows),
        "total_objective_rows": len(cycle_rows),
        "remaining_counted_cycle_budget": max(
            0,
            int(max_cycles_per_invocation) - len(counted_rows),
        ),
    }


def load_successor_effective_next_objective(workspace_root: str | Path | None) -> dict[str, Any]:
    if not workspace_root:
        return {}
    return load_json(_workspace_paths(Path(workspace_root))["effective_next_objective_path"])


def _active_effective_next_objective(workspace_root: Path) -> dict[str, Any]:
    payload = load_successor_effective_next_objective(workspace_root)
    if not payload:
        return {}
    reseed_state = str(payload.get("reseed_state", "")).strip()
    execution_state = str(payload.get("execution_state", "")).strip().lower()
    if not bool(payload.get("continuation_authorized", False)):
        return {}
    if reseed_state not in {RESEED_APPROVED_STATE, RESEED_MATERIALIZED_STATE}:
        return {}
    if execution_state in {"completed", "rejected", "deferred", "superseded"}:
        return {}
    if not str(payload.get("objective_id", "")).strip():
        return {}
    return payload


def _current_objective_context(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
) -> dict[str, Any]:
    active_objective = _active_effective_next_objective(workspace_root)
    if active_objective:
        objective_id = str(active_objective.get("objective_id", "")).strip()
        return {
            "source_kind": OBJECTIVE_SOURCE_APPROVED_RESEED,
            "objective_id": objective_id,
            "objective_class": _objective_class_from_objective_id(objective_id),
            "title": str(active_objective.get("title", "")).strip() or _humanize_objective_id(objective_id),
            "rationale": str(active_objective.get("rationale", "")).strip(),
            "authorization_origin": str(active_objective.get("authorization_origin", "")).strip(),
            "approved_from_request_path": str(active_objective.get("reseed_request_path", "")).strip(),
            "approved_from_decision_path": str(active_objective.get("reseed_decision_path", "")).strip(),
            "approved_from_lineage_path": str(active_objective.get("continuation_lineage_path", "")).strip(),
            "effective_next_objective_path": str(
                _workspace_paths(workspace_root)["effective_next_objective_path"]
            ),
            "payload": active_objective,
        }
    objective_id = str(current_directive.get("directive_id", "")).strip()
    title = (
        str(current_directive.get("clarified_intent_summary", "")).strip()
        or str(current_directive.get("directive_text", "")).strip()
        or _humanize_objective_id(objective_id)
    )
    return {
        "source_kind": OBJECTIVE_SOURCE_DIRECTIVE,
        "objective_id": objective_id,
        "objective_class": _objective_class_from_objective_id(objective_id),
        "title": title,
        "rationale": "Using the original directive as the current bounded objective context.",
        "authorization_origin": "",
        "approved_from_request_path": "",
        "approved_from_decision_path": "",
        "approved_from_lineage_path": "",
        "effective_next_objective_path": "",
        "payload": {},
    }


def _resolve_reference_target_consumption(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    current_objective: dict[str, Any] | None = None,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    reference_target = load_json(paths["reference_target_path"])
    admitted_candidate = load_json(paths["admitted_candidate_path"])
    baseline_comparison = load_json(paths["baseline_comparison_path"])
    current_objective_payload = dict(
        current_objective
        or _current_objective_context(
            current_directive=current_directive,
            workspace_root=workspace_root,
        )
    )
    protected_live_baseline_reference_id = str(
        reference_target.get(
            "protected_live_baseline_reference_id",
            "current_bounded_baseline_expectations_v1",
        )
    ).strip() or "current_bounded_baseline_expectations_v1"
    protected_live_baseline_source_kind = str(
        reference_target.get(
            "protected_live_baseline_source_kind",
            "internal_bounded_reference_pack",
        )
    ).strip() or "internal_bounded_reference_pack"
    protected_live_baseline_title = str(
        reference_target.get(
            "protected_live_baseline_title",
            _humanize_objective_id(protected_live_baseline_reference_id),
        )
    ).strip() or _humanize_objective_id(protected_live_baseline_reference_id)
    protected_live_baseline_path_hint = str(
        reference_target.get("protected_live_baseline_path_hint", "")
    ).strip()

    preferred_reference_target_id = str(
        reference_target.get("preferred_reference_target_id", "")
    ).strip()
    preferred_reference_target_source_kind = str(
        reference_target.get("preferred_reference_target_source_kind", "")
    ).strip()
    preferred_reference_target_path = str(
        reference_target.get("preferred_reference_target_path", "")
    ).strip()
    future_runs_should_compare_against = str(
        reference_target.get("future_runs_should_compare_against", "")
    ).strip() or protected_live_baseline_reference_id
    reference_target_state = str(reference_target.get("reference_target_state", "")).strip()
    reference_target_eligible = bool(
        reference_target.get("eligible_as_future_reference_target", False)
    )

    consumption_state = REFERENCE_TARGET_MISSING_STATE
    active_bounded_reference_target_id = protected_live_baseline_reference_id
    active_bounded_reference_target_source_kind = protected_live_baseline_source_kind
    active_bounded_reference_target_title = protected_live_baseline_title
    active_bounded_reference_target_path = protected_live_baseline_path_hint
    active_bounded_reference_target_origin = "protected_bounded_baseline"
    fallback_to_protected_baseline = True
    fallback_reason = ""

    if not reference_target:
        fallback_reason = (
            "no future reference target artifact exists yet, so this run falls back to the current protected bounded baseline reference"
        )
    elif reference_target_eligible:
        candidate_path = preferred_reference_target_path or str(paths["admitted_candidate_path"])
        candidate_payload = (
            load_json(Path(candidate_path))
            if candidate_path and Path(candidate_path).exists()
            else dict(admitted_candidate)
        )
        candidate_recorded = bool(candidate_payload.get("admitted_candidate_recorded", False))
        candidate_handoff_ready = bool(candidate_payload.get("handoff_ready", False)) or (
            str(candidate_payload.get("handoff_state", "")).strip()
            == ADMITTED_CANDIDATE_HANDOFF_READY_STATE
        )
        candidate_stronger = bool(
            baseline_comparison.get("stronger_than_current_bounded_baseline", False)
        )
        if not candidate_payload:
            consumption_state = REFERENCE_TARGET_MISSING_STATE
            fallback_reason = (
                "the future reference target artifact points to a missing admitted-candidate artifact, so this run falls back to the protected bounded baseline"
            )
        elif not candidate_recorded or not candidate_handoff_ready or not candidate_stronger:
            consumption_state = REFERENCE_TARGET_INCOMPATIBLE_STATE
            fallback_reason = (
                "the future reference target exists but is not compatible for consumption in this run because the admitted candidate is not fully recorded, handoff-ready, or stronger-than-baseline"
            )
        else:
            consumption_state = REFERENCE_TARGET_CONSUMED_STATE
            active_bounded_reference_target_id = (
                preferred_reference_target_id
                or str(candidate_payload.get("admitted_candidate_id", "")).strip()
                or protected_live_baseline_reference_id
            )
            active_bounded_reference_target_source_kind = (
                preferred_reference_target_source_kind or "admitted_candidate"
            )
            active_bounded_reference_target_title = (
                str(candidate_payload.get("candidate_bundle_identity", "")).strip()
                or _humanize_objective_id(active_bounded_reference_target_id)
            )
            active_bounded_reference_target_path = candidate_path or str(
                paths["admitted_candidate_path"]
            )
            active_bounded_reference_target_origin = "admitted_candidate"
            fallback_to_protected_baseline = False
    else:
        consumption_state = (
            REFERENCE_TARGET_FALLBACK_PROTECTED_BASELINE_STATE
            if reference_target
            else REFERENCE_TARGET_MISSING_STATE
        )
        fallback_reason = (
            "the recorded future reference target is not currently eligible, so this run continues against the protected bounded baseline reference"
        )

    comparison_basis = (
        "admitted_candidate_bounded_reference_target"
        if consumption_state == REFERENCE_TARGET_CONSUMED_STATE
        else "protected_bounded_baseline_reference"
    )
    if not reference_target and not reference_target_state:
        reference_target_state = REFERENCE_TARGET_MISSING_STATE

    return {
        "schema_name": SUCCESSOR_REFERENCE_TARGET_CONSUMPTION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_REFERENCE_TARGET_CONSUMPTION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")).strip(),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_objective_id": str(current_objective_payload.get("objective_id", "")).strip(),
        "current_objective_source_kind": str(
            current_objective_payload.get("source_kind", "")
        ).strip(),
        "current_objective_class": str(
            current_objective_payload.get("objective_class", "")
        ).strip(),
        "reference_target_artifact_path": str(paths["reference_target_path"]),
        "admitted_candidate_artifact_path": str(paths["admitted_candidate_path"]),
        "baseline_comparison_path": str(paths["baseline_comparison_path"]),
        "reference_target_state": reference_target_state,
        "reference_target_eligible": reference_target_eligible,
        "preferred_reference_target_id": preferred_reference_target_id,
        "preferred_reference_target_source_kind": preferred_reference_target_source_kind,
        "preferred_reference_target_path": preferred_reference_target_path,
        "future_runs_should_compare_against": future_runs_should_compare_against,
        "consumption_state": consumption_state,
        "comparison_basis": comparison_basis,
        "consumed_admitted_candidate": consumption_state == REFERENCE_TARGET_CONSUMED_STATE,
        "fallback_to_protected_baseline": fallback_to_protected_baseline,
        "fallback_reason": fallback_reason,
        "active_bounded_reference_target_id": active_bounded_reference_target_id,
        "active_bounded_reference_target_source_kind": active_bounded_reference_target_source_kind,
        "active_bounded_reference_target_title": active_bounded_reference_target_title,
        "active_bounded_reference_target_path": active_bounded_reference_target_path,
        "active_bounded_reference_target_origin": active_bounded_reference_target_origin,
        "protected_live_baseline_reference_id": protected_live_baseline_reference_id,
        "protected_live_baseline_source_kind": protected_live_baseline_source_kind,
        "protected_live_baseline_title": protected_live_baseline_title,
        "protected_live_baseline_path_hint": protected_live_baseline_path_hint,
        "protected_live_baseline_unchanged": True,
        "live_baseline_replacement_performed": False,
        "explicit_non_live_baseline_replacement_note": "This run may consume an admitted candidate as the working bounded reference target, but it does not replace or mutate the protected/live baseline.",
    }


def _effective_objective_stage(objective_id: str) -> dict[str, Any]:
    objective = str(objective_id or "").strip()
    if objective == "prepare_candidate_promotion_bundle":
        return {
            "stage_id": "candidate_promotion_bundle",
            "cycle_kind": "planning_only",
            "next_recommended_cycle": "operator_review_required",
            "title": "Materialize the candidate promotion bundle for operator review.",
            "work_item_id": "successor_candidate_promotion_bundle",
            "rationale": "The operator approved a bounded promotion-bundle objective derived from the prior completed successor package.",
        }
    stage_map = {
        "materialize_workspace_local_implementation": "first_implementation_bundle",
        "review_and_expand_workspace_local_implementation": "first_implementation_bundle",
        "strengthen_successor_test_coverage": "successor_readiness_bundle",
        "improve_successor_package_readiness": "successor_readiness_bundle",
        "refine_successor_docs_readiness": "successor_readiness_bundle",
        "refine_successor_artifact_index_consistency": "successor_readiness_bundle",
        "improve_successor_handoff_completeness": "successor_readiness_bundle",
        "materialize_successor_package_readiness_bundle": "successor_readiness_bundle",
        "plan_successor_package_gap_closure": "continuation_gap_analysis",
    }
    stage_id = str(stage_map.get(objective, "")).strip()
    if not stage_id:
        return {}
    cycle_kind = "planning_only" if stage_id in {"initial_planning_bundle", "continuation_gap_analysis"} else "implementation_bearing"
    return {
        "stage_id": stage_id,
        "cycle_kind": cycle_kind,
        "next_recommended_cycle": objective,
        "title": _humanize_objective_id(objective),
        "work_item_id": objective,
        "rationale": "The operator approved this bounded next objective from the prior review artifacts.",
    }


def _is_compact_auto_continue_objective(objective_class: str) -> bool:
    return str(objective_class or "").strip() in COMPACT_AUTO_CONTINUE_OBJECTIVE_CLASSES


def _quality_objective_completion_blueprint(
    *,
    objective_id: str,
) -> dict[str, Any]:
    objective = str(objective_id or "").strip()
    blueprints = {
        "review_and_expand_workspace_local_implementation": {
            "objective_title": "Review and expand workspace-local implementation",
            "deliverable_id": "workspace_review_quality_bundle",
            "expected_skill_pack_id": INTERNAL_SUCCESSOR_WORKSPACE_REVIEW_SKILL_PACK_ID,
            "required_relative_paths": [
                "src/successor_shell/workspace_contract.py",
                "tests/test_workspace_contract.py",
                "docs/successor_shell_iteration_notes.md",
                "artifacts/workspace_artifact_index_latest.json",
            ],
        },
        "strengthen_successor_test_coverage": {
            "objective_title": "Strengthen successor test coverage",
            "deliverable_id": "successor_test_quality_bundle",
            "expected_skill_pack_id": INTERNAL_SUCCESSOR_TEST_STRENGTHENING_SKILL_PACK_ID,
            "required_relative_paths": [
                "tests/test_workspace_contract.py",
                "tests/test_successor_manifest.py",
                "artifacts/workspace_artifact_index_latest.json",
            ],
        },
        "improve_successor_package_readiness": {
            "objective_title": "Improve successor package readiness",
            "deliverable_id": "successor_readiness_quality_bundle",
            "expected_skill_pack_id": INTERNAL_SUCCESSOR_MANIFEST_QUALITY_SKILL_PACK_ID,
            "required_relative_paths": [
                "src/successor_shell/successor_manifest.py",
                "tests/test_successor_manifest.py",
                "docs/successor_package_readiness_note.md",
                "artifacts/workspace_artifact_index_latest.json",
                "artifacts/successor_delivery_manifest_latest.json",
                "artifacts/successor_readiness_evaluation_latest.json",
            ],
        },
        "refine_successor_docs_readiness": {
            "objective_title": "Refine successor docs readiness",
            "deliverable_id": "successor_docs_readiness_bundle",
            "expected_skill_pack_id": INTERNAL_SUCCESSOR_DOCS_READINESS_SKILL_PACK_ID,
            "required_relative_paths": [
                "docs/successor_package_readiness_note.md",
                "docs/successor_docs_readiness_review.md",
                "artifacts/workspace_artifact_index_latest.json",
            ],
        },
        "refine_successor_artifact_index_consistency": {
            "objective_title": "Refine successor artifact index consistency",
            "deliverable_id": "successor_artifact_index_consistency_bundle",
            "expected_skill_pack_id": INTERNAL_SUCCESSOR_ARTIFACT_INDEX_CONSISTENCY_SKILL_PACK_ID,
            "required_relative_paths": [
                "artifacts/workspace_artifact_index_latest.json",
                "artifacts/successor_artifact_index_consistency_latest.json",
            ],
        },
        "improve_successor_handoff_completeness": {
            "objective_title": "Improve successor handoff completeness",
            "deliverable_id": "successor_handoff_completeness_bundle",
            "expected_skill_pack_id": INTERNAL_SUCCESSOR_HANDOFF_COMPLETENESS_SKILL_PACK_ID,
            "required_relative_paths": [
                "docs/successor_promotion_bundle_note.md",
                "docs/successor_handoff_completeness_note.md",
                "artifacts/successor_candidate_promotion_bundle_latest.json",
                "artifacts/successor_admitted_candidate_handoff_latest.json",
            ],
        },
    }
    return dict(blueprints.get(objective, {}))


def _evaluate_approved_quality_objective_completion(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    objective_context: dict[str, Any],
    reference_target_context: dict[str, Any],
) -> dict[str, Any]:
    objective_id = str(objective_context.get("objective_id", "")).strip()
    blueprint = _quality_objective_completion_blueprint(objective_id=objective_id)
    if not blueprint:
        return {}
    paths = _workspace_paths(workspace_root)
    latest_skill_pack_result = load_json(paths["skill_pack_result_path"])
    latest_quality_improvement_summary = load_json(paths["quality_improvement_summary_path"])
    latest_quality_gap_summary = load_json(paths["quality_gap_summary_path"])
    selected_skill_pack_id = str(
        latest_skill_pack_result.get("selected_skill_pack_id", "")
    ).strip()
    result_state = str(latest_skill_pack_result.get("result_state", "")).strip()
    improvement_state = str(
        latest_quality_improvement_summary.get("improvement_state", "")
    ).strip()
    required_relative_paths = [
        str(item).strip()
        for item in list(blueprint.get("required_relative_paths", []))
        if str(item).strip()
    ]
    evidence_rows = [
        _relative_path_status(workspace_root, relative_path)
        for relative_path in required_relative_paths
    ]
    missing_relative_paths = [
        str(item.get("relative_path", ""))
        for item in evidence_rows
        if not bool(item.get("present", False))
    ]
    details: list[str] = []
    expected_skill_pack_id = str(blueprint.get("expected_skill_pack_id", "")).strip()
    if selected_skill_pack_id != expected_skill_pack_id:
        details.append(
            "expected bounded skill pack "
            f"{expected_skill_pack_id or '<none>'} but observed "
            f"{selected_skill_pack_id or '<none>'}"
        )
    if result_state != "complete":
        details.append(
            f"skill-pack result remains {result_state or '<none>'} instead of complete"
        )
    if improvement_state != "complete":
        details.append(
            "quality improvement remains "
            f"{improvement_state or '<none>'} instead of complete"
        )
    if missing_relative_paths:
        details.append("missing required paths: " + ", ".join(missing_relative_paths))
    completed = not details
    reason = (
        f"approved quality objective {objective_id} is complete and its bounded skill-pack evidence is present inside the active workspace"
        if completed
        else f"approved quality objective {objective_id} still requires reentry before its bounded skill-pack evidence is complete"
    )
    return {
        "schema_name": COMPLETION_EVALUATION_SCHEMA_NAME,
        "schema_version": COMPLETION_EVALUATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "completion_pack_id": f"approved_quality_objective_{objective_id}_v1",
        "completion_rule": "approved_quality_objective_skill_pack_evidence_present_inside_active_workspace",
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_root": str(workspace_root),
        "completed": completed,
        "reason": reason,
        "partial_completion_states": ([] if completed else ["approved_quality_objective_pending"]),
        "required_deliverable_count": len(evidence_rows),
        "missing_required_deliverables": (
            [
                {
                    "deliverable_id": str(blueprint.get("deliverable_id", "")),
                    "title": str(blueprint.get("objective_title", objective_id)),
                    "missing_evidence_relative_paths": missing_relative_paths,
                }
            ]
            if missing_relative_paths or not completed
            else []
        ),
        "deliverable_checks": [
            {
                "deliverable_id": str(blueprint.get("deliverable_id", "")),
                "title": str(blueprint.get("objective_title", objective_id)),
                "required": True,
                "completed": completed,
                "missing_evidence_relative_paths": missing_relative_paths,
                "evidence_paths_present": [
                    str(item.get("absolute_path", ""))
                    for item in evidence_rows
                    if bool(item.get("present", False))
                ],
                "evidence_rows": evidence_rows,
                "expected_skill_pack_id": expected_skill_pack_id,
                "selected_skill_pack_id": selected_skill_pack_id,
                "skill_pack_result_state": result_state,
                "quality_improvement_state": improvement_state,
                "quality_gap_id": str(latest_quality_gap_summary.get("quality_gap_id", "")),
                "details": details or ["passed"],
            }
        ],
        "recommended_stop": completed,
        "current_objective": objective_context,
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        "working_reference_target": dict(reference_target_context),
        "reference_target_consumption_state": str(
            reference_target_context.get("consumption_state", "")
        ),
        "active_bounded_reference_target_id": str(
            reference_target_context.get("active_bounded_reference_target_id", "")
        ),
        "protected_live_baseline_reference_id": str(
            reference_target_context.get("protected_live_baseline_reference_id", "")
        ),
        "comparison_basis": str(reference_target_context.get("comparison_basis", "")),
    }


def _evaluate_current_objective_completion(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    completion_pack: dict[str, Any],
    objective_context: dict[str, Any] | None = None,
    reference_target_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    objective_context = dict(
        objective_context
        or _current_objective_context(
            current_directive=current_directive,
            workspace_root=workspace_root,
        )
    )
    reference_target_context = dict(
        reference_target_context
        or _resolve_reference_target_consumption(
            current_directive=current_directive,
            workspace_root=workspace_root,
            current_objective=objective_context,
        )
    )
    base_evaluation = _evaluate_successor_completion(
        current_directive=current_directive,
        workspace_root=workspace_root,
        completion_pack=completion_pack,
        reference_target_context=reference_target_context,
    )
    if objective_context["source_kind"] != OBJECTIVE_SOURCE_APPROVED_RESEED:
        return {
            **base_evaluation,
            "current_objective": objective_context,
        }

    objective_id = str(objective_context.get("objective_id", "")).strip()
    paths = _workspace_paths(workspace_root)
    if objective_id == "prepare_candidate_promotion_bundle":
        refresh_eligibility = _evaluate_revised_candidate_refresh_eligibility(
            workspace_root=workspace_root,
            current_objective=objective_context,
            completion_evaluation={"completed": True},
            reference_target_context=reference_target_context,
        )
        revised_candidate_refresh = bool(refresh_eligibility.get("eligible", False))
        required_relative_paths = (
            [
                "docs/successor_promotion_bundle_note.md",
                "artifacts/successor_revised_candidate_bundle_latest.json",
                "artifacts/successor_revised_candidate_handoff_latest.json",
                "artifacts/successor_revised_candidate_comparison_latest.json",
                "artifacts/successor_revised_candidate_promotion_summary_latest.json",
            ]
            if revised_candidate_refresh
            else [
                "docs/successor_promotion_bundle_note.md",
                "artifacts/successor_candidate_promotion_bundle_latest.json",
            ]
        )
        evidence_rows = [
            _relative_path_status(workspace_root, relative_path)
            for relative_path in required_relative_paths
        ]
        missing_relative_paths = [
            str(item.get("relative_path", ""))
            for item in evidence_rows
            if not bool(item.get("present", False))
        ]
        lineage_failure_relative_paths: list[str] = []
        lineage_details: list[str] = []
        if revised_candidate_refresh:
            active_reference_target_id = str(
                reference_target_context.get("active_bounded_reference_target_id", "")
            ).strip()
            revised_candidate_bundle = load_json(paths["revised_candidate_bundle_path"])
            revised_candidate_comparison = load_json(
                paths["revised_candidate_comparison_path"]
            )
            revised_candidate_promotion_summary = load_json(
                paths["revised_candidate_promotion_summary_path"]
            )
            if not active_reference_target_id:
                lineage_details.append(
                    "no active bounded reference target id was available for revised candidate refresh lineage validation"
                )
            else:
                bundle_prior_candidate_id = str(
                    revised_candidate_bundle.get("prior_admitted_candidate_id", "")
                ).strip()
                if bundle_prior_candidate_id != active_reference_target_id:
                    lineage_failure_relative_paths.append(
                        "artifacts/successor_revised_candidate_bundle_latest.json"
                    )
                    lineage_details.append(
                        "the revised candidate bundle is tied to an older admitted candidate lineage and must be refreshed against the current active bounded reference target"
                    )
                comparison_prior_candidate_id = str(
                    revised_candidate_comparison.get("prior_admitted_candidate_id", "")
                ).strip()
                if (
                    comparison_prior_candidate_id
                    and comparison_prior_candidate_id != active_reference_target_id
                ):
                    lineage_failure_relative_paths.append(
                        "artifacts/successor_revised_candidate_comparison_latest.json"
                    )
                    lineage_details.append(
                        "the revised candidate comparison artifact still references an older admitted candidate lineage"
                    )
                promotion_prior_candidate_id = str(
                    revised_candidate_promotion_summary.get(
                        "prior_admitted_candidate_id", ""
                    )
                ).strip()
                if (
                    promotion_prior_candidate_id
                    and promotion_prior_candidate_id != active_reference_target_id
                ):
                    lineage_failure_relative_paths.append(
                        "artifacts/successor_revised_candidate_promotion_summary_latest.json"
                    )
                    lineage_details.append(
                        "the revised candidate promotion summary still references an older admitted candidate lineage"
                    )
            lineage_failure_relative_paths = _unique_string_list(
                lineage_failure_relative_paths
            )
        all_missing_relative_paths = _unique_string_list(
            missing_relative_paths + lineage_failure_relative_paths
        )
        completed = not all_missing_relative_paths
        deliverable_id = (
            "revised_candidate_promotion_bundle"
            if revised_candidate_refresh
            else "candidate_promotion_bundle"
        )
        deliverable_title = (
            "Revised candidate promotion bundle"
            if revised_candidate_refresh
            else "Candidate promotion bundle"
        )
        reason = (
            (
                "approved revised candidate promotion bundle deliverables are present inside the active workspace"
                if revised_candidate_refresh
                else "approved candidate promotion bundle deliverables are present inside the active workspace"
            )
            if completed
            else (
                (
                    "approved revised candidate promotion bundle deliverables remain incomplete or stale relative to the current active bounded reference target inside the active workspace"
                    if revised_candidate_refresh and lineage_failure_relative_paths
                    else "approved revised candidate promotion bundle deliverables remain incomplete inside the active workspace"
                )
                if revised_candidate_refresh
                else "approved candidate promotion bundle deliverables remain incomplete inside the active workspace"
            )
        )
        return {
            "schema_name": COMPLETION_EVALUATION_SCHEMA_NAME,
            "schema_version": COMPLETION_EVALUATION_SCHEMA_VERSION,
            "generated_at": _now(),
            "completion_pack_id": (
                "approved_next_objective_prepare_revised_candidate_promotion_bundle_v1"
                if revised_candidate_refresh
                else "approved_next_objective_prepare_candidate_promotion_bundle_v1"
            ),
            "completion_rule": "approved_reseed_objective_deliverables_present_inside_active_workspace",
            "directive_id": str(current_directive.get("directive_id", "")),
            "workspace_root": str(workspace_root),
            "completed": completed,
            "reason": reason,
            "partial_completion_states": (
                []
                if completed
                else [
                    (
                        "approved_revised_candidate_promotion_bundle_pending"
                        if revised_candidate_refresh
                        else "approved_candidate_promotion_bundle_pending"
                    )
                ]
            ),
            "required_deliverable_count": len(evidence_rows),
            "missing_required_deliverables": [
                {
                    "deliverable_id": deliverable_id,
                    "title": deliverable_title,
                    "missing_evidence_relative_paths": all_missing_relative_paths,
                    "lineage_validation_failures": lineage_details,
                }
            ]
            if all_missing_relative_paths
            else [],
            "deliverable_checks": [
                {
                    "deliverable_id": deliverable_id,
                    "title": deliverable_title,
                    "required": True,
                    "completed": completed,
                    "missing_evidence_relative_paths": all_missing_relative_paths,
                    "evidence_paths_present": [
                        str(item.get("absolute_path", ""))
                        for item in evidence_rows
                        if bool(item.get("present", False))
                    ],
                    "evidence_rows": evidence_rows,
                    "lineage_validation_reference_target_id": str(
                        reference_target_context.get(
                            "active_bounded_reference_target_id", ""
                        )
                    ),
                    "lineage_validation_failures": lineage_details,
                }
            ],
            "recommended_stop": completed,
            "current_objective": objective_context,
            "effective_next_objective_path": str(paths["effective_next_objective_path"]),
            "working_reference_target": dict(reference_target_context),
            "reference_target_consumption_state": str(
                reference_target_context.get("consumption_state", "")
            ),
            "active_bounded_reference_target_id": str(
                reference_target_context.get("active_bounded_reference_target_id", "")
            ),
            "protected_live_baseline_reference_id": str(
                reference_target_context.get("protected_live_baseline_reference_id", "")
            ),
            "comparison_basis": str(
                reference_target_context.get("comparison_basis", "")
            ),
        }
    approved_quality_completion = _evaluate_approved_quality_objective_completion(
        current_directive=current_directive,
        workspace_root=workspace_root,
        objective_context=objective_context,
        reference_target_context=reference_target_context,
    )
    if approved_quality_completion:
        return approved_quality_completion
    return {
        **base_evaluation,
        "completed": False,
        "recommended_stop": False,
        "reason": (
            f"approved next objective {objective_id} remains active and requires a bounded continuation cycle "
            "before completion can be re-evaluated"
        ),
        "current_objective": objective_context,
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        "working_reference_target": dict(reference_target_context),
        "reference_target_consumption_state": str(
            reference_target_context.get("consumption_state", "")
        ),
        "active_bounded_reference_target_id": str(
            reference_target_context.get("active_bounded_reference_target_id", "")
        ),
        "protected_live_baseline_reference_id": str(
            reference_target_context.get("protected_live_baseline_reference_id", "")
        ),
        "comparison_basis": str(reference_target_context.get("comparison_basis", "")),
    }


def _derive_review_next_objective(
    *,
    review_pack: dict[str, Any],
    promotable: bool,
    promotion_state: str,
    weak_areas: list[dict[str, Any]],
    completion_evaluation: dict[str, Any],
    next_recommended_cycle: str,
    current_objective: dict[str, Any],
) -> dict[str, Any]:
    templates = _objective_template_rows(review_pack)
    if str(current_objective.get("source_kind", "")).strip() == OBJECTIVE_SOURCE_APPROVED_RESEED:
        objective_id = ""
        rationale = (
            "The approved bounded continuation objective is complete enough for review in this slice, "
            "but any further continuation remains explicitly operator-reviewed and is not proposed automatically."
        )
        return {
            "schema_name": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME,
            "schema_version": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION,
            "generated_at": _now(),
            "proposal_state": PROMOTION_DEFERRED_STATE,
            "objective_id": objective_id,
            "objective_class": "",
            "title": "No automatic follow-on objective proposed",
            "rationale": rationale,
            "promotion_recommendation_state": promotion_state,
            "operator_review_required": True,
            "authorized_for_automatic_execution": False,
            "bounded_objective_complete": bool(completion_evaluation.get("completed", False)),
        }
    objective_id = ""

    if promotable:
        objective_id = "prepare_candidate_promotion_bundle"
    else:
        for item in weak_areas:
            candidate = str(item.get("failure_objective_id", "")).strip()
            if candidate:
                objective_id = candidate
                break
        if not objective_id:
            candidate = str(next_recommended_cycle).strip()
            if candidate and candidate != "operator_review_required":
                objective_id = candidate

    template = dict(templates.get(objective_id, {}))
    proposal_state = NEXT_OBJECTIVE_AVAILABLE_STATE if objective_id else PROMOTION_DEFERRED_STATE
    rationale = (
        str(template.get("rationale", "")).strip()
        if template
        else (
            "No further bounded objective is proposed automatically in this slice."
            if not objective_id
            else f"Proposed from the current bounded review state: {objective_id}."
        )
    )
    if not objective_id and bool(completion_evaluation.get("completed", False)):
        rationale = (
            "The bounded objective is complete, but continuation remains explicitly review-gated "
            "until an operator accepts a next bounded objective."
        )

    return {
        "schema_name": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME,
        "schema_version": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION,
        "generated_at": _now(),
        "proposal_state": proposal_state,
        "objective_id": objective_id,
        "objective_class": _objective_class_from_objective_id(objective_id),
        "title": str(template.get("title", "")).strip() or _humanize_objective_id(objective_id) or "No next bounded objective proposed",
        "rationale": rationale,
        "promotion_recommendation_state": promotion_state,
        "operator_review_required": True,
        "authorized_for_automatic_execution": False,
        "bounded_objective_complete": bool(completion_evaluation.get("completed", False)),
    }


def _derive_reference_target_quality_follow_on_objective(
    *,
    review_pack: dict[str, Any],
    workspace_root: Path,
    current_objective: dict[str, Any],
    completion_evaluation: dict[str, Any],
    promotion_state: str,
    reference_target_context: dict[str, Any],
) -> dict[str, Any]:
    if str(current_objective.get("source_kind", "")).strip() == OBJECTIVE_SOURCE_APPROVED_RESEED:
        return {}
    if not bool(completion_evaluation.get("completed", False)):
        return {}
    if (
        str(reference_target_context.get("consumption_state", "")).strip()
        != REFERENCE_TARGET_CONSUMED_STATE
    ):
        return {}
    if (
        str(reference_target_context.get("active_bounded_reference_target_origin", "")).strip()
        != "admitted_candidate"
    ):
        return {}
    paths = _workspace_paths(workspace_root)
    latest_skill_pack_result = load_json(paths["skill_pack_result_path"])
    if str(latest_skill_pack_result.get("selected_skill_pack_id", "")).strip():
        return {}
    templates = _objective_template_rows(review_pack)
    objective_id = "improve_successor_package_readiness"
    template = dict(templates.get(objective_id, {}))
    active_reference_target_id = str(
        reference_target_context.get("active_bounded_reference_target_id", "")
    ).strip() or "current_bounded_baseline_expectations_v1"
    return {
        "schema_name": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME,
        "schema_version": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION,
        "generated_at": _now(),
        "proposal_state": NEXT_OBJECTIVE_AVAILABLE_STATE,
        "proposal_source": "reference_target_quality_follow_on",
        "objective_id": objective_id,
        "objective_class": _objective_class_from_objective_id(objective_id),
        "title": str(template.get("title", "")).strip()
        or _humanize_objective_id(objective_id)
        or "Improve successor package readiness",
        "rationale": (
            "The bounded successor package is complete and the admitted candidate is now the active "
            f"bounded reference target (`{active_reference_target_id}`), but no bounded successor-quality "
            "revision has yet been recorded relative to that reference target. Propose a conservative "
            "workspace-local readiness and manifest quality follow-on before repeating promotion-bundle work."
        ),
        "promotion_recommendation_state": promotion_state,
        "operator_review_required": True,
        "authorized_for_automatic_execution": False,
        "bounded_objective_complete": True,
    }


def _derive_revised_candidate_refresh_follow_on_objective(
    *,
    review_pack: dict[str, Any],
    workspace_root: Path,
    current_objective: dict[str, Any],
    completion_evaluation: dict[str, Any],
    promotion_state: str,
    reference_target_context: dict[str, Any],
) -> dict[str, Any]:
    current_objective_source_kind = str(current_objective.get("source_kind", "")).strip()
    if current_objective_source_kind not in {
        OBJECTIVE_SOURCE_APPROVED_RESEED,
        OBJECTIVE_SOURCE_DIRECTIVE,
    }:
        return {}
    if not bool(completion_evaluation.get("completed", False)):
        return {}
    current_objective_id = str(current_objective.get("objective_id", "")).strip()
    if not current_objective_id or current_objective_id == "prepare_candidate_promotion_bundle":
        return {}
    eligibility = _evaluate_revised_candidate_refresh_eligibility(
        workspace_root=workspace_root,
        current_objective=current_objective,
        completion_evaluation=completion_evaluation,
        reference_target_context=reference_target_context,
    )
    if not bool(eligibility.get("eligible", False)):
        return {}
    templates = _objective_template_rows(review_pack)
    objective_id = "prepare_candidate_promotion_bundle"
    template = dict(templates.get(objective_id, {}))
    prior_admitted_candidate_id = str(
        eligibility.get("prior_admitted_candidate_id", "")
    ).strip() or "current_bounded_baseline_expectations_v1"
    improved_dimension_ids = list(eligibility.get("improved_dimension_ids", []))
    improved_dimension_summary = ", ".join(improved_dimension_ids[:3]) if improved_dimension_ids else "<none>"
    return {
        "schema_name": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME,
        "schema_version": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION,
        "generated_at": _now(),
        "proposal_state": NEXT_OBJECTIVE_AVAILABLE_STATE,
        "proposal_source": "revised_candidate_refresh",
        "objective_id": objective_id,
        "objective_class": _objective_class_from_objective_id(objective_id),
        "title": str(template.get("title", "")).strip()
        or _humanize_objective_id(objective_id)
        or "Prepare a revised candidate promotion bundle",
        "rationale": (
            "The just-completed bounded quality-improvement objective now leaves the successor "
            "materially stronger in aggregate relative to the currently admitted bounded reference "
            f"target (`{prior_admitted_candidate_id}`). Propose a refreshed candidate promotion "
            "bundle so the improved successor can re-enter explicit promotion and admission review. "
            f"Improved dimensions: {improved_dimension_summary}."
        ),
        "promotion_recommendation_state": promotion_state,
        "operator_review_required": True,
        "authorized_for_automatic_execution": False,
        "bounded_objective_complete": True,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "quality_composite_state": str(
            eligibility.get("quality_composite_state", "")
        ).strip(),
        "materially_stronger_than_reference_target_in_aggregate": bool(
            eligibility.get("materially_stronger_in_aggregate", False)
        ),
        "quality_roadmap_path": str(_workspace_paths(workspace_root)["quality_roadmap_path"]),
        "quality_composite_evaluation_path": str(
            _workspace_paths(workspace_root)["quality_composite_evaluation_path"]
        ),
    }


def _derive_approved_quality_chain_follow_on_objective(
    *,
    review_pack: dict[str, Any],
    workspace_root: Path,
    current_objective: dict[str, Any],
    completion_evaluation: dict[str, Any],
    promotion_state: str,
    reference_target_context: dict[str, Any],
) -> dict[str, Any]:
    if str(current_objective.get("source_kind", "")).strip() != OBJECTIVE_SOURCE_APPROVED_RESEED:
        return {}
    if not bool(completion_evaluation.get("completed", False)):
        return {}
    objective_id = str(current_objective.get("objective_id", "")).strip()
    paths = _workspace_paths(workspace_root)
    latest_skill_pack_result = load_json(paths["skill_pack_result_path"])
    latest_quality_improvement_summary = load_json(
        paths["quality_improvement_summary_path"]
    )
    selected_skill_pack_id = str(
        latest_skill_pack_result.get("selected_skill_pack_id", "")
    ).strip()
    if str(latest_skill_pack_result.get("result_state", "")).strip() != "complete":
        return {}
    if str(latest_quality_improvement_summary.get("improvement_state", "")).strip() != "complete":
        return {}

    roadmap_outputs = _evaluate_successor_quality_roadmap_state(
        workspace_root=workspace_root,
        current_objective=current_objective,
        reference_target_context=reference_target_context,
        latest_skill_pack_invocation=load_json(paths["skill_pack_invocation_path"]),
        latest_skill_pack_result=latest_skill_pack_result,
        latest_quality_gap_summary=load_json(paths["quality_gap_summary_path"]),
        latest_quality_improvement_summary=latest_quality_improvement_summary,
    )
    next_pack_plan = dict(roadmap_outputs.get("next_pack_plan", {}))
    next_objective_id = str(next_pack_plan.get("selected_objective_id", "")).strip()
    rationale = ""
    if next_objective_id and next_objective_id != objective_id:
        selected_dimension_title = str(
            next_pack_plan.get("selected_dimension_title", "")
        ).strip()
        selected_skill_pack_title = str(
            next_pack_plan.get("selected_skill_pack_id", "")
        ).strip()
        rationale = (
            "The bounded quality-improvement roadmap now recommends the next highest-priority unresolved "
            "dimension after the just-completed successor-quality step. "
            f"Selected dimension: {selected_dimension_title or '<unknown>'}. "
            f"Selected bounded skill pack: {selected_skill_pack_title or '<unknown>'}."
        )
    if not next_objective_id:
        return {}

    templates = _objective_template_rows(review_pack)
    template = dict(templates.get(next_objective_id, {}))
    active_reference_target_id = str(
        reference_target_context.get("active_bounded_reference_target_id", "")
    ).strip() or "current_bounded_baseline_expectations_v1"
    return {
        "schema_name": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME,
        "schema_version": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION,
        "generated_at": _now(),
        "proposal_state": NEXT_OBJECTIVE_AVAILABLE_STATE,
        "proposal_source": "quality_roadmap_follow_on",
        "objective_id": next_objective_id,
        "objective_class": _objective_class_from_objective_id(next_objective_id),
        "title": str(template.get("title", "")).strip()
        or _humanize_objective_id(next_objective_id)
        or _humanize_objective_id(next_objective_id),
        "rationale": (
            f"{rationale} Active bounded reference target: `{active_reference_target_id}`."
        ),
        "promotion_recommendation_state": promotion_state,
        "operator_review_required": True,
        "authorized_for_automatic_execution": False,
        "bounded_objective_complete": True,
        "quality_roadmap_path": str(paths["quality_roadmap_path"]),
        "quality_next_pack_plan_path": str(paths["quality_next_pack_plan_path"]),
        "selected_quality_dimension_id": str(
            next_pack_plan.get("selected_dimension_id", "")
        ).strip(),
    }


def _evaluate_successor_review_and_promotion(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    stop_reason: str,
    stop_detail: str,
    next_recommended_cycle: str,
    completion_evaluation: dict[str, Any],
    cycle_rows: list[dict[str, Any]],
    latest_summary_artifact_path: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    completion_objective = dict(completion_evaluation.get("current_objective", {}))
    if str(completion_objective.get("objective_id", "")).strip():
        current_objective = {
            "source_kind": str(completion_objective.get("source_kind", "")).strip()
            or OBJECTIVE_SOURCE_DIRECTIVE,
            "objective_id": str(completion_objective.get("objective_id", "")).strip(),
            "objective_class": str(
                completion_objective.get("objective_class", "")
            ).strip()
            or _objective_class_from_objective_id(
                str(completion_objective.get("objective_id", "")).strip()
            ),
            "title": str(completion_objective.get("title", "")).strip()
            or _humanize_objective_id(
                str(completion_objective.get("objective_id", "")).strip()
            ),
            "rationale": str(completion_objective.get("rationale", "")).strip(),
            "authorization_origin": str(
                completion_objective.get("authorization_origin", "")
            ).strip(),
            "approved_from_request_path": str(
                completion_objective.get("approved_from_request_path", "")
            ).strip(),
            "approved_from_decision_path": str(
                completion_objective.get("approved_from_decision_path", "")
            ).strip(),
            "approved_from_lineage_path": str(
                completion_objective.get("approved_from_lineage_path", "")
            ).strip(),
            "effective_next_objective_path": str(
                completion_objective.get("effective_next_objective_path", "")
            ).strip(),
            "payload": dict(completion_objective.get("payload", {})),
        }
    else:
        current_objective = _current_objective_context(
            current_directive=current_directive,
            workspace_root=workspace_root,
        )
    review_pack, review_source = _load_internal_knowledge_pack(
        session=session,
        source_id=INTERNAL_SUCCESSOR_PROMOTION_REVIEW_SOURCE_ID,
        expected_schema_name=SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    review_state_model = dict(review_pack.get("review_status_model", {}))
    artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    readiness_summary = load_json(paths["readiness_summary_path"])
    delivery_manifest = load_json(paths["delivery_manifest_path"])
    cycle_history_summary = _cycle_history_summary(cycle_rows)
    cycle_output_paths = _collect_cycle_output_paths(cycle_rows)
    outputs_outside_workspace = [
        item
        for item in cycle_output_paths
        if item and not _is_under_path(Path(str(item)), workspace_root)
    ]
    completion_ready = (
        bool(completion_evaluation.get("completed", False))
        and bool(readiness_summary.get("completion_ready", False))
        and bool(delivery_manifest.get("completion_ready", False))
    )

    check_rows: list[dict[str, Any]] = []
    weak_areas: list[dict[str, Any]] = []
    for item in list(review_pack.get("promotion_checks", [])):
        row = dict(item)
        check_id = str(row.get("check_id", "")).strip()
        if not check_id:
            continue
        title = str(row.get("title", check_id))
        required_relative_paths = [
            str(path).strip() for path in list(row.get("required_relative_paths", [])) if str(path).strip()
        ]
        evidence_rows = [_relative_path_status(workspace_root, relative_path) for relative_path in required_relative_paths]
        missing_relative_paths = [
            str(entry.get("relative_path", ""))
            for entry in evidence_rows
            if not bool(entry.get("present", False))
        ]
        passed = True
        details: list[str] = []
        if missing_relative_paths:
            passed = False
            details.append("missing required paths: " + ", ".join(missing_relative_paths))
        expected_stop_reason = str(row.get("expected_stop_reason", "")).strip()
        if expected_stop_reason and stop_reason != expected_stop_reason:
            passed = False
            details.append(f"expected stop reason {expected_stop_reason} but observed {stop_reason or '<none>'}")
        disallowed_stop_reasons = [
            str(value).strip() for value in list(row.get("disallowed_stop_reasons", [])) if str(value).strip()
        ]
        if disallowed_stop_reasons and stop_reason in disallowed_stop_reasons:
            passed = False
            details.append(f"observed disallowed stop reason {stop_reason}")
        if bool(row.get("requires_output_within_workspace", False)) and outputs_outside_workspace:
            passed = False
            details.append("output paths escaped the bounded active workspace")
        if bool(row.get("requires_completion_ready", False)) and not completion_ready:
            passed = False
            details.append("completion claims are not backed by readiness artifacts")

        check_row = {
            "check_id": check_id,
            "title": title,
            "passed": passed,
            "required_relative_paths": required_relative_paths,
            "missing_relative_paths": missing_relative_paths,
            "details": "; ".join(details) if details else "passed",
            "failure_objective_id": str(row.get("failure_objective_id", "")).strip(),
        }
        check_rows.append(check_row)
        if not passed:
            weak_areas.append(check_row)

    promotable = bool(check_rows) and not weak_areas
    review_status = str(review_state_model.get("review_status_default", REVIEW_STATUS_REQUIRED)).strip() or REVIEW_STATUS_REQUIRED
    promotion_state = (
        str(review_state_model.get("promotion_recommended_state", PROMOTION_RECOMMENDED_STATE)).strip()
        if promotable
        else str(review_state_model.get("promotion_not_recommended_state", PROMOTION_NOT_RECOMMENDED_STATE)).strip()
    ) or (PROMOTION_RECOMMENDED_STATE if promotable else PROMOTION_NOT_RECOMMENDED_STATE)
    candidate_context = _load_active_candidate_bundle_context(workspace_root=workspace_root)
    candidate_bundle_variant = str(candidate_context.get("variant", "")).strip() or "candidate_promotion_bundle"
    candidate_bundle_manifest_path = str(candidate_context.get("bundle_path", "")).strip()
    candidate_bundle_identity = str(
        candidate_context.get("candidate_bundle_identity", "")
    ).strip()
    prior_admitted_candidate_id = str(
        candidate_context.get("prior_admitted_candidate_id", "")
    ).strip()
    reference_target_context = _resolve_reference_target_consumption(
        current_directive=current_directive,
        workspace_root=workspace_root,
        current_objective=current_objective,
    )
    proposal_payload: dict[str, Any] = {}
    if promotable:
        proposal_payload = _derive_revised_candidate_refresh_follow_on_objective(
            review_pack=review_pack,
            workspace_root=workspace_root,
            current_objective=current_objective,
            completion_evaluation=completion_evaluation,
            promotion_state=promotion_state,
            reference_target_context=reference_target_context,
        )
    if not proposal_payload:
        proposal_payload = _derive_approved_quality_chain_follow_on_objective(
            review_pack=review_pack,
            workspace_root=workspace_root,
            current_objective=current_objective,
            completion_evaluation=completion_evaluation,
            promotion_state=promotion_state,
            reference_target_context=reference_target_context,
        )
    if promotable and not proposal_payload:
        proposal_payload = _derive_reference_target_quality_follow_on_objective(
            review_pack=review_pack,
            workspace_root=workspace_root,
            current_objective=current_objective,
            completion_evaluation=completion_evaluation,
            promotion_state=promotion_state,
            reference_target_context=reference_target_context,
        )
    if not proposal_payload:
        proposal_payload = _derive_review_next_objective(
            review_pack=review_pack,
            promotable=promotable,
            promotion_state=promotion_state,
            weak_areas=weak_areas,
            completion_evaluation=completion_evaluation,
            next_recommended_cycle=next_recommended_cycle,
            current_objective=current_objective,
        )
    bounded_deliverables_present = [
        str(item.get("relative_path", ""))
        for item in list(delivery_manifest.get("deliverables", []))
        if bool(item.get("present", False))
    ]
    recommendation_rationale = (
        "The bounded successor package satisfies the current bounded completion and review rubric, so promotion is recommended for explicit operator review."
        if promotable
        else (
            "Promotion is not recommended yet because bounded review checks still report missing or weak areas."
            if weak_areas
            else "Promotion is not recommended because review evidence is incomplete."
        )
    )
    confidence = "conservative_high" if promotable else ("conservative_medium" if bool(completion_evaluation.get("completed", False)) else "conservative_low")

    recommendation_payload = {
        "schema_name": SUCCESSOR_PROMOTION_RECOMMENDATION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_PROMOTION_RECOMMENDATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "completed_objective_id": str(current_objective.get("objective_id", "")),
        "completed_objective_source_kind": str(current_objective.get("source_kind", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "review_status": review_status,
        "promotion_recommendation_state": promotion_state,
        "promotion_recommended": promotable,
        "confidence": confidence,
        "rationale": recommendation_rationale,
        "bounded_objective_complete": bool(completion_evaluation.get("completed", False)),
        "stop_reason": stop_reason,
        "stop_detail": stop_detail,
        "protected_surfaces_untouched": not outputs_outside_workspace,
        "outputs_within_active_workspace": not outputs_outside_workspace,
        "operator_review_required": True,
        "requires_operator_review_before_promotion": True,
        "criteria_results": check_rows,
        "weak_areas": weak_areas,
        "knowledge_pack_source": review_source,
        "candidate_bundle_identity": candidate_bundle_identity,
        "candidate_bundle_variant": candidate_bundle_variant,
        "candidate_bundle_manifest_path": candidate_bundle_manifest_path,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
    }
    review_summary = {
        "schema_name": SUCCESSOR_REVIEW_SUMMARY_SCHEMA_NAME,
        "schema_version": SUCCESSOR_REVIEW_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "completed_objective_id": str(current_objective.get("objective_id", "")),
        "completed_objective_source_kind": str(current_objective.get("source_kind", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "cycle_history_summary": cycle_history_summary,
        "latest_summary_artifact_path": str(latest_summary_artifact_path or ""),
        "bounded_deliverables_present": bounded_deliverables_present,
        "missing_or_weak_areas": weak_areas,
        "review_status": review_status,
        "promotion_recommendation_state": promotion_state,
        "promotion_recommended": promotable,
        "operator_review_required": True,
        "next_objective_state": str(proposal_payload.get("proposal_state", PROMOTION_DEFERRED_STATE)),
        "next_objective_id": str(proposal_payload.get("objective_id", "")),
        "next_objective_title": str(proposal_payload.get("title", "")),
        "bounded_objective_complete": bool(completion_evaluation.get("completed", False)),
        "stop_reason": stop_reason,
        "stop_detail": stop_detail,
        "completion_evaluation": completion_evaluation,
        "artifact_index_path": str(paths["workspace_artifact_index_path"]),
        "artifact_count": int(artifact_index.get("artifact_count", 0) or 0),
        "knowledge_pack_source": review_source,
        "candidate_bundle_identity": candidate_bundle_identity,
        "candidate_bundle_variant": candidate_bundle_variant,
        "candidate_bundle_manifest_path": candidate_bundle_manifest_path,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
    }
    return {
        "review_summary": review_summary,
        "promotion_recommendation": recommendation_payload,
        "next_objective_proposal": {
            **proposal_payload,
            "directive_id": str(current_directive.get("directive_id", "")),
            "completed_objective_id": str(current_objective.get("objective_id", "")),
            "completed_objective_source_kind": str(current_objective.get("source_kind", "")),
            "workspace_id": str(workspace_root.name),
            "workspace_root": str(workspace_root),
        },
    }


def _materialize_successor_review_outputs(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    stop_reason: str,
    stop_detail: str,
    next_recommended_cycle: str,
    completion_evaluation: dict[str, Any],
    cycle_rows: list[dict[str, Any]],
    latest_summary_artifact_path: str,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    review_payloads = _evaluate_successor_review_and_promotion(
        current_directive=current_directive,
        workspace_root=workspace_root,
        session=session,
        stop_reason=stop_reason,
        stop_detail=stop_detail,
        next_recommended_cycle=next_recommended_cycle,
        completion_evaluation=completion_evaluation,
        cycle_rows=cycle_rows,
        latest_summary_artifact_path=latest_summary_artifact_path,
    )
    latest_paths = [
        (paths["review_summary_path"], dict(review_payloads.get("review_summary", {})), "successor_review_summary_json"),
        (
            paths["promotion_recommendation_path"],
            dict(review_payloads.get("promotion_recommendation", {})),
            "successor_promotion_recommendation_json",
        ),
        (
            paths["next_objective_proposal_path"],
            dict(review_payloads.get("next_objective_proposal", {})),
            "successor_next_objective_proposal_json",
        ),
    ]
    _event(
        runtime_event_log_path,
        event_type="successor_review_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        stop_reason=stop_reason,
    )
    for artifact_path, artifact_payload, artifact_kind in latest_paths:
        _write_json(
            artifact_path,
            artifact_payload,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id="successor_review_and_promotion",
            artifact_kind=artifact_kind,
        )

    latest_cycle_index = int(_cycle_history_summary(cycle_rows).get("latest_cycle_index", 0) or 0)
    if latest_cycle_index > 0:
        cycle_prefix = paths["cycles_root"] / f"cycle_{latest_cycle_index:03d}"
        archive_rows = [
            (cycle_prefix.with_name(f"{cycle_prefix.name}_successor_review_summary.json"), dict(review_payloads.get("review_summary", {}))),
            (
                cycle_prefix.with_name(f"{cycle_prefix.name}_successor_promotion_recommendation.json"),
                dict(review_payloads.get("promotion_recommendation", {})),
            ),
            (
                cycle_prefix.with_name(f"{cycle_prefix.name}_successor_next_objective_proposal.json"),
                dict(review_payloads.get("next_objective_proposal", {})),
            ),
        ]
        for artifact_path, artifact_payload in archive_rows:
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    review_summary = dict(review_payloads.get("review_summary", {}))
    promotion_recommendation = dict(review_payloads.get("promotion_recommendation", {}))
    next_objective_proposal = dict(review_payloads.get("next_objective_proposal", {}))
    _event(
        runtime_event_log_path,
        event_type="successor_review_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        review_status=str(review_summary.get("review_status", "")),
        review_summary_path=str(paths["review_summary_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="promotion_recommendation_recorded",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        promotion_recommendation_state=str(promotion_recommendation.get("promotion_recommendation_state", "")),
        recommendation_path=str(paths["promotion_recommendation_path"]),
        reason=str(promotion_recommendation.get("rationale", "")),
    )
    _event(
        runtime_event_log_path,
        event_type="next_objective_proposed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        proposed_objective_id=str(next_objective_proposal.get("objective_id", "")),
        next_objective_state=str(next_objective_proposal.get("proposal_state", "")),
        next_objective_proposal_path=str(paths["next_objective_proposal_path"]),
        reason=str(next_objective_proposal.get("rationale", "")),
    )
    return {
        **review_payloads,
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
    }


def _baseline_admission_applicable(workspace_root: Path) -> bool:
    return bool(load_json(_workspace_paths(workspace_root)["promotion_bundle_manifest_path"]))


def _derive_baseline_remediation_proposal(
    *,
    admission_pack: dict[str, Any],
    admission_recommended: bool,
    weak_areas: list[dict[str, Any]],
    current_directive: dict[str, Any],
    workspace_root: Path,
    candidate_bundle: dict[str, Any],
    review_summary: dict[str, Any],
    admission_recommendation_state: str,
) -> dict[str, Any]:
    templates = _remediation_template_rows(admission_pack)
    objective_id = ""
    if not admission_recommended:
        for item in weak_areas:
            candidate = str(item.get("failure_objective_id", "")).strip()
            if candidate:
                objective_id = candidate
                break
        if not objective_id:
            objective_id = "prepare_candidate_promotion_bundle"
    template = dict(templates.get(objective_id, {}))
    proposal_state = "remediation_not_required" if admission_recommended else REMEDIATION_REQUIRED_STATE
    rationale = (
        "No bounded remediation proposal is required because the candidate bundle satisfies the current conservative admission rubric."
        if admission_recommended
        else (
            str(template.get("rationale", "")).strip()
            or "Admission is not recommended yet, so a bounded remediation objective is proposed conservatively."
        )
    )
    return {
        "schema_name": SUCCESSOR_BASELINE_REMEDIATION_PROPOSAL_SCHEMA_NAME,
        "schema_version": SUCCESSOR_BASELINE_REMEDIATION_PROPOSAL_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "candidate_bundle_objective_id": str(candidate_bundle.get("objective_id", "")),
        "completed_objective_id": str(review_summary.get("completed_objective_id", "")),
        "completed_objective_source_kind": str(
            review_summary.get("completed_objective_source_kind", "")
        ),
        "proposal_state": proposal_state,
        "remediation_required": not admission_recommended,
        "objective_id": objective_id,
        "objective_class": _objective_class_from_objective_id(objective_id),
        "title": str(template.get("title", "")).strip()
        or (
            _humanize_objective_id(objective_id)
            if objective_id
            else "No remediation proposal required"
        ),
        "rationale": rationale,
        "admission_recommendation_state": admission_recommendation_state,
        "operator_review_required": True,
        "authorized_for_automatic_execution": False,
        "weak_areas": weak_areas,
    }


def _evaluate_successor_baseline_admission(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    stop_reason: str,
    stop_detail: str,
    completion_evaluation: dict[str, Any],
    cycle_rows: list[dict[str, Any]],
    latest_summary_artifact_path: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    candidate_context = _load_active_candidate_bundle_context(workspace_root=workspace_root)
    candidate_bundle = dict(candidate_context.get("bundle_payload", {}))
    candidate_bundle_manifest_path = str(
        candidate_context.get("bundle_path", "")
    ).strip() or str(paths["promotion_bundle_manifest_path"])
    candidate_bundle_variant = str(candidate_context.get("variant", "")).strip() or (
        "candidate_promotion_bundle"
    )
    prior_admitted_candidate_id = str(
        candidate_context.get("prior_admitted_candidate_id", "")
    ).strip()
    revised_candidate_bundle_path = str(
        candidate_context.get("bundle_path", "")
    ).strip() if candidate_bundle_variant == "revised_candidate" else ""
    revised_candidate_handoff_path = str(
        candidate_context.get("handoff_path", "")
    ).strip()
    revised_candidate_comparison_path = str(
        candidate_context.get("comparison_path", "")
    ).strip()
    revised_candidate_promotion_summary_path = str(
        candidate_context.get("promotion_summary_path", "")
    ).strip()
    if not candidate_bundle:
        return {}

    review_summary = load_json(paths["review_summary_path"])
    promotion_recommendation = load_json(paths["promotion_recommendation_path"])
    continuation_lineage = load_json(paths["continuation_lineage_path"])
    delivery_manifest = load_json(paths["delivery_manifest_path"])
    readiness_summary = load_json(paths["readiness_summary_path"])
    artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    admission_pack, admission_source = _load_internal_knowledge_pack(
        session=session,
        source_id=INTERNAL_SUCCESSOR_BASELINE_ADMISSION_SOURCE_ID,
        expected_schema_name=SUCCESSOR_BASELINE_ADMISSION_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=SUCCESSOR_BASELINE_ADMISSION_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    status_model = dict(admission_pack.get("admission_status_model", {}))
    cycle_history_summary = _cycle_history_summary(cycle_rows)
    cycle_output_paths = _collect_cycle_output_paths(cycle_rows)
    outputs_outside_workspace = [
        item
        for item in cycle_output_paths
        if item and not _is_under_path(Path(str(item)), workspace_root)
    ]
    completion_ready = (
        bool(completion_evaluation.get("completed", False))
        and bool(readiness_summary.get("completion_ready", False))
        and bool(delivery_manifest.get("completion_ready", False))
    )
    bundle_completion_ready = bool(candidate_bundle.get("completion_ready", False))
    promotion_state = str(
        promotion_recommendation.get("promotion_recommendation_state", "")
    ).strip()
    review_status = str(review_summary.get("review_status", "")).strip()
    strength_signal = all(
        [
            bool(completion_evaluation.get("completed", False)),
            completion_ready,
            bundle_completion_ready,
            promotion_state == PROMOTION_RECOMMENDED_STATE,
            bool(review_summary.get("promotion_recommended", False)),
            bool(candidate_bundle.get("bundle_items", [])),
            bool(artifact_index.get("artifact_count", 0)),
            bool(continuation_lineage),
        ]
    )

    check_rows: list[dict[str, Any]] = []
    weak_areas: list[dict[str, Any]] = []
    for item in list(admission_pack.get("admission_checks", [])):
        row = dict(item)
        check_id = str(row.get("check_id", "")).strip()
        if not check_id:
            continue
        required_relative_paths = [
            str(path).strip()
            for path in list(row.get("required_relative_paths", []))
            if str(path).strip()
        ]
        evidence_rows = [
            _relative_path_status(workspace_root, relative_path)
            for relative_path in required_relative_paths
        ]
        missing_relative_paths = [
            str(entry.get("relative_path", ""))
            for entry in evidence_rows
            if not bool(entry.get("present", False))
        ]
        passed = True
        details: list[str] = []
        if missing_relative_paths:
            passed = False
            details.append("missing required paths: " + ", ".join(missing_relative_paths))
        expected_stop_reason = str(row.get("expected_stop_reason", "")).strip()
        if expected_stop_reason and stop_reason != expected_stop_reason:
            passed = False
            details.append(
                f"expected stop reason {expected_stop_reason} but observed {stop_reason or '<none>'}"
            )
        disallowed_stop_reasons = [
            str(value).strip()
            for value in list(row.get("disallowed_stop_reasons", []))
            if str(value).strip()
        ]
        if disallowed_stop_reasons and stop_reason in disallowed_stop_reasons:
            passed = False
            details.append(f"observed disallowed stop reason {stop_reason}")
        expected_promotion_state = str(
            row.get("expected_promotion_recommendation_state", "")
        ).strip()
        if expected_promotion_state and promotion_state != expected_promotion_state:
            passed = False
            details.append(
                "expected promotion recommendation "
                f"{expected_promotion_state} but observed {promotion_state or '<none>'}"
            )
        expected_review_status = str(row.get("expected_review_status", "")).strip()
        if expected_review_status and review_status != expected_review_status:
            passed = False
            details.append(
                f"expected review status {expected_review_status} but observed {review_status or '<none>'}"
            )
        if bool(row.get("requires_output_within_workspace", False)) and outputs_outside_workspace:
            passed = False
            details.append("output paths escaped the bounded active workspace")
        if bool(row.get("requires_completion_ready", False)) and not completion_ready:
            passed = False
            details.append("completion claims are not backed by readiness artifacts")
        if (
            bool(row.get("requires_bundle_manifest_completion_ready", False))
            and not bundle_completion_ready
        ):
            passed = False
            details.append("candidate promotion bundle is not marked completion_ready")
        if bool(row.get("requires_admission_strength_signal", False)) and not strength_signal:
            passed = False
            details.append("bounded baseline strength signal is not yet present")
        check_row = {
            "check_id": check_id,
            "title": str(row.get("title", check_id)),
            "passed": passed,
            "required_relative_paths": required_relative_paths,
            "missing_relative_paths": missing_relative_paths,
            "details": "; ".join(details) if details else "passed",
            "failure_objective_id": str(row.get("failure_objective_id", "")).strip(),
        }
        check_rows.append(check_row)
        if not passed:
            weak_areas.append(check_row)

    admission_recommended = bool(check_rows) and not weak_areas
    admission_review_state = (
        str(status_model.get("review_required_state", ADMISSION_REVIEW_REQUIRED_STATE)).strip()
        or ADMISSION_REVIEW_REQUIRED_STATE
    )
    admission_recommendation_state = (
        str(
            status_model.get(
                "recommended_state" if admission_recommended else "not_recommended_state",
                ADMISSION_RECOMMENDED_STATE
                if admission_recommended
                else ADMISSION_NOT_RECOMMENDED_STATE,
            )
        ).strip()
        or (
            ADMISSION_RECOMMENDED_STATE
            if admission_recommended
            else ADMISSION_NOT_RECOMMENDED_STATE
        )
    )
    remediation_proposal = _derive_baseline_remediation_proposal(
        admission_pack=admission_pack,
        admission_recommended=admission_recommended,
        weak_areas=weak_areas,
        current_directive=current_directive,
        workspace_root=workspace_root,
        candidate_bundle=candidate_bundle,
        review_summary=review_summary,
        admission_recommendation_state=admission_recommendation_state,
    )
    bounded_deliverables_present = _unique_string_list(
        [
            *[
                str(item)
                for item in list(candidate_bundle.get("bundle_items", []))
                if str(item).strip()
            ],
            *[
                str(item.get("relative_path", ""))
                for item in list(delivery_manifest.get("deliverables", []))
                if bool(item.get("present", False))
            ],
        ]
    )
    review_inputs_used = [
        {"artifact_kind": "candidate_promotion_bundle", "path": candidate_bundle_manifest_path},
        {"artifact_kind": "successor_review_summary", "path": str(paths["review_summary_path"])},
        {"artifact_kind": "successor_promotion_recommendation", "path": str(paths["promotion_recommendation_path"])},
        {"artifact_kind": "successor_continuation_lineage", "path": str(paths["continuation_lineage_path"])},
        {"artifact_kind": "successor_readiness_evaluation", "path": str(paths["readiness_summary_path"])},
        {"artifact_kind": "successor_delivery_manifest", "path": str(paths["delivery_manifest_path"])},
        {"artifact_kind": "workspace_artifact_index", "path": str(paths["workspace_artifact_index_path"])},
        {"artifact_kind": "knowledge_pack", "path": str(admission_source.get("path_hint", ""))},
        *(
            [
                {"artifact_kind": "revised_candidate_handoff", "path": revised_candidate_handoff_path},
                {"artifact_kind": "revised_candidate_comparison", "path": revised_candidate_comparison_path},
                {
                    "artifact_kind": "revised_candidate_promotion_summary",
                    "path": revised_candidate_promotion_summary_path,
                },
            ]
            if candidate_bundle_variant == "revised_candidate"
            else []
        ),
    ]
    recommendation_rationale = (
        (
            "The revised candidate bundle satisfies the current conservative bounded admission rubric and is recommended as the next admitted bounded reference candidate pending explicit operator approval."
            if candidate_bundle_variant == "revised_candidate"
            else "The candidate promotion bundle satisfies the current conservative bounded admission rubric and is recommended as an admitted bounded baseline candidate pending explicit operator approval."
        )
        if admission_recommended
        else (
            (
                "Re-admission is not recommended yet because the revised candidate bundle still has bounded missing or weak areas that should be remediated before admission."
                if candidate_bundle_variant == "revised_candidate"
                else "Baseline admission is not recommended yet because the candidate promotion bundle still has bounded missing or weak areas that should be remediated before admission."
            )
            if weak_areas
            else "Baseline admission is not recommended because candidate-bundle admission evidence is incomplete."
        )
    )
    confidence = (
        "conservative_high"
        if admission_recommended
        else (
            "conservative_medium"
            if bool(completion_evaluation.get("completed", False))
            else "conservative_low"
        )
    )
    review_payload = {
        "schema_name": SUCCESSOR_BASELINE_ADMISSION_REVIEW_SCHEMA_NAME,
        "schema_version": SUCCESSOR_BASELINE_ADMISSION_REVIEW_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "candidate_bundle_objective_id": str(candidate_bundle.get("objective_id", "")),
        "candidate_bundle_identity": _candidate_bundle_identity_from_payload(candidate_bundle),
        "candidate_bundle_variant": candidate_bundle_variant,
        "candidate_bundle_manifest_path": candidate_bundle_manifest_path,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "revised_candidate_bundle_path": revised_candidate_bundle_path,
        "revised_candidate_handoff_path": revised_candidate_handoff_path,
        "revised_candidate_comparison_path": revised_candidate_comparison_path,
        "revised_candidate_promotion_summary_path": revised_candidate_promotion_summary_path,
        "completed_objective_id": str(review_summary.get("completed_objective_id", "")),
        "completed_objective_source_kind": str(
            review_summary.get("completed_objective_source_kind", "")
        ),
        "cycle_history_summary": cycle_history_summary,
        "latest_summary_artifact_path": str(latest_summary_artifact_path or ""),
        "review_inputs_used": review_inputs_used,
        "candidate_deliverables_present": bounded_deliverables_present,
        "missing_or_weak_areas": weak_areas,
        "admission_review_state": admission_review_state,
        "admission_recommendation_state": admission_recommendation_state,
        "admission_recommended": admission_recommended,
        "candidate_materially_stronger_than_bounded_baseline": strength_signal,
        "operator_review_required": True,
        "operator_review_required_before_admission": True,
        "admitted_bounded_baseline_candidate": False,
        "remediation_required": not admission_recommended,
        "remediation_proposal_objective_id": str(remediation_proposal.get("objective_id", "")),
        "remediation_proposal_title": str(remediation_proposal.get("title", "")),
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "continuation_lineage_path": str(paths["continuation_lineage_path"]),
        "knowledge_pack_source": admission_source,
        "stop_reason": stop_reason,
        "stop_detail": stop_detail,
        "completion_evaluation": completion_evaluation,
    }
    recommendation_payload = {
        "schema_name": SUCCESSOR_BASELINE_ADMISSION_RECOMMENDATION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_BASELINE_ADMISSION_RECOMMENDATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "candidate_bundle_objective_id": str(candidate_bundle.get("objective_id", "")),
        "candidate_bundle_identity": _candidate_bundle_identity_from_payload(candidate_bundle),
        "candidate_bundle_variant": candidate_bundle_variant,
        "candidate_bundle_manifest_path": candidate_bundle_manifest_path,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "revised_candidate_bundle_path": revised_candidate_bundle_path,
        "completed_objective_id": str(review_summary.get("completed_objective_id", "")),
        "completed_objective_source_kind": str(
            review_summary.get("completed_objective_source_kind", "")
        ),
        "admission_review_state": admission_review_state,
        "admission_recommendation_state": admission_recommendation_state,
        "admission_recommended": admission_recommended,
        "confidence": confidence,
        "rationale": recommendation_rationale,
        "operator_review_required": True,
        "admitted_bounded_baseline_candidate": False,
        "candidate_materially_stronger_than_bounded_baseline": strength_signal,
        "criteria_results": check_rows,
        "weak_areas": weak_areas,
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "continuation_lineage_path": str(paths["continuation_lineage_path"]),
        "knowledge_pack_source": admission_source,
    }
    decision_payload = {
        "schema_name": SUCCESSOR_BASELINE_ADMISSION_DECISION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_BASELINE_ADMISSION_DECISION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "candidate_bundle_objective_id": str(candidate_bundle.get("objective_id", "")),
        "candidate_bundle_identity": _candidate_bundle_identity_from_payload(candidate_bundle),
        "candidate_bundle_variant": candidate_bundle_variant,
        "candidate_bundle_manifest_path": candidate_bundle_manifest_path,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "revised_candidate_bundle_path": revised_candidate_bundle_path,
        "completed_objective_id": str(review_summary.get("completed_objective_id", "")),
        "completed_objective_source_kind": str(
            review_summary.get("completed_objective_source_kind", "")
        ),
        "admission_decision_state": admission_review_state,
        "operator_decision": "pending_review",
        "operator_note": "",
        "decision_actor": "pending_operator_review",
        "admission_recommendation_state": admission_recommendation_state,
        "admission_recommended": admission_recommended,
        "operator_review_required": True,
        "admitted_bounded_baseline_candidate": False,
        "baseline_mutation_performed": False,
        "remediation_required": not admission_recommended,
        "remediation_proposal_path": str(paths["baseline_remediation_proposal_path"]),
        "review_path": str(paths["baseline_admission_review_path"]),
        "recommendation_path": str(paths["baseline_admission_recommendation_path"]),
    }
    return {
        "review": review_payload,
        "recommendation": recommendation_payload,
        "decision": decision_payload,
        "remediation_proposal": remediation_proposal,
    }


def _materialize_successor_baseline_admission_outputs(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    stop_reason: str,
    stop_detail: str,
    completion_evaluation: dict[str, Any],
    cycle_rows: list[dict[str, Any]],
    latest_summary_artifact_path: str,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    if not _baseline_admission_applicable(workspace_root):
        return {
            "review": load_json(paths["baseline_admission_review_path"]),
            "recommendation": load_json(paths["baseline_admission_recommendation_path"]),
            "decision": load_json(paths["baseline_admission_decision_path"]),
            "remediation_proposal": load_json(paths["baseline_remediation_proposal_path"]),
            "review_path": str(paths["baseline_admission_review_path"]),
            "recommendation_path": str(paths["baseline_admission_recommendation_path"]),
            "decision_path": str(paths["baseline_admission_decision_path"]),
            "remediation_proposal_path": str(paths["baseline_remediation_proposal_path"]),
        }

    payloads = _evaluate_successor_baseline_admission(
        current_directive=current_directive,
        workspace_root=workspace_root,
        session=session,
        stop_reason=stop_reason,
        stop_detail=stop_detail,
        completion_evaluation=completion_evaluation,
        cycle_rows=cycle_rows,
        latest_summary_artifact_path=latest_summary_artifact_path,
    )
    if not payloads:
        return {
            "review": {},
            "recommendation": {},
            "decision": {},
            "remediation_proposal": {},
            "review_path": str(paths["baseline_admission_review_path"]),
            "recommendation_path": str(paths["baseline_admission_recommendation_path"]),
            "decision_path": str(paths["baseline_admission_decision_path"]),
            "remediation_proposal_path": str(paths["baseline_remediation_proposal_path"]),
        }

    latest_paths = [
        (
            paths["baseline_admission_review_path"],
            dict(payloads.get("review", {})),
            "successor_baseline_admission_review_json",
        ),
        (
            paths["baseline_admission_recommendation_path"],
            dict(payloads.get("recommendation", {})),
            "successor_baseline_admission_recommendation_json",
        ),
        (
            paths["baseline_admission_decision_path"],
            dict(payloads.get("decision", {})),
            "successor_baseline_admission_decision_json",
        ),
        (
            paths["baseline_remediation_proposal_path"],
            dict(payloads.get("remediation_proposal", {})),
            "successor_baseline_remediation_proposal_json",
        ),
    ]
    _event(
        runtime_event_log_path,
        event_type="successor_baseline_admission_review_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        candidate_bundle_manifest_path=str(paths["promotion_bundle_manifest_path"]),
    )
    for artifact_path, artifact_payload, artifact_kind in latest_paths:
        _write_json(
            artifact_path,
            artifact_payload,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id="successor_baseline_admission_review",
            artifact_kind=artifact_kind,
        )

    latest_cycle_index = int(_cycle_history_summary(cycle_rows).get("latest_cycle_index", 0) or 0)
    if latest_cycle_index > 0:
        cycle_prefix = paths["cycles_root"] / f"cycle_{latest_cycle_index:03d}"
        archive_rows = [
            (
                cycle_prefix.with_name(f"{cycle_prefix.name}_successor_baseline_admission_review.json"),
                dict(payloads.get("review", {})),
            ),
            (
                cycle_prefix.with_name(f"{cycle_prefix.name}_successor_baseline_admission_recommendation.json"),
                dict(payloads.get("recommendation", {})),
            ),
            (
                cycle_prefix.with_name(f"{cycle_prefix.name}_successor_baseline_admission_decision.json"),
                dict(payloads.get("decision", {})),
            ),
            (
                cycle_prefix.with_name(f"{cycle_prefix.name}_successor_baseline_remediation_proposal.json"),
                dict(payloads.get("remediation_proposal", {})),
            ),
        ]
        for artifact_path, artifact_payload in archive_rows:
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    recommendation_payload = dict(payloads.get("recommendation", {}))
    remediation_payload = dict(payloads.get("remediation_proposal", {}))
    decision_payload = dict(payloads.get("decision", {}))
    _event(
        runtime_event_log_path,
        event_type="successor_baseline_admission_recommendation_recorded",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        admission_recommendation_state=str(
            recommendation_payload.get("admission_recommendation_state", "")
        ),
        recommendation_path=str(paths["baseline_admission_recommendation_path"]),
        reason=str(recommendation_payload.get("rationale", "")),
    )
    _event(
        runtime_event_log_path,
        event_type="successor_baseline_remediation_proposal_materialized",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        remediation_objective_id=str(remediation_payload.get("objective_id", "")),
        remediation_state=str(remediation_payload.get("proposal_state", "")),
        remediation_proposal_path=str(paths["baseline_remediation_proposal_path"]),
        reason=str(remediation_payload.get("rationale", "")),
    )
    _event(
        runtime_event_log_path,
        event_type="successor_baseline_admission_review_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        admission_review_state=str(decision_payload.get("admission_decision_state", "")),
        admission_recommendation_state=str(
            recommendation_payload.get("admission_recommendation_state", "")
        ),
        admission_review_path=str(paths["baseline_admission_review_path"]),
        candidate_bundle_manifest_path=str(
            decision_payload.get("candidate_bundle_manifest_path", "")
        ).strip()
        or str(paths["promotion_bundle_manifest_path"]),
    )
    return {
        **payloads,
        "review_path": str(paths["baseline_admission_review_path"]),
        "recommendation_path": str(paths["baseline_admission_recommendation_path"]),
        "decision_path": str(paths["baseline_admission_decision_path"]),
        "remediation_proposal_path": str(paths["baseline_remediation_proposal_path"]),
    }


def materialize_successor_baseline_admission_decision(
    *,
    workspace_root: str | Path,
    operator_decision: str,
    operator_note: str = "",
    actor: str = "operator_web_ui",
) -> dict[str, Any]:
    workspace_root_path = Path(workspace_root)
    paths = _workspace_paths(workspace_root_path)
    admission_review = load_json(paths["baseline_admission_review_path"])
    admission_recommendation = load_json(paths["baseline_admission_recommendation_path"])
    remediation_proposal = load_json(paths["baseline_remediation_proposal_path"])
    candidate_context = _load_active_candidate_bundle_context(workspace_root=workspace_root_path)
    candidate_bundle = dict(candidate_context.get("bundle_payload", {}))
    candidate_bundle_manifest_path = str(
        candidate_context.get("bundle_path", "")
    ).strip() or str(paths["promotion_bundle_manifest_path"])
    candidate_bundle_variant = str(candidate_context.get("variant", "")).strip() or (
        "candidate_promotion_bundle"
    )
    candidate_bundle_identity = str(
        candidate_context.get("candidate_bundle_identity", "")
    ).strip() or _candidate_bundle_identity_from_payload(candidate_bundle)
    prior_admitted_candidate_id = str(
        candidate_context.get("prior_admitted_candidate_id", "")
    ).strip()
    revised_candidate_bundle_path = str(
        candidate_context.get("bundle_path", "")
    ).strip() if candidate_bundle_variant == "revised_candidate" else ""
    if not admission_review or not admission_recommendation:
        raise GovernedExecutionFailure(
            "baseline admission decision requires existing admission review artifacts",
            summary_artifact_path=str(paths["baseline_admission_review_path"]),
        )
    decision_key = str(operator_decision or "").strip().lower()
    if decision_key not in {"approve", "defer", "reject"}:
        raise GovernedExecutionFailure(
            "unsupported baseline admission decision; expected approve, defer, or reject"
        )
    recommendation_state = str(
        admission_recommendation.get("admission_recommendation_state", "")
    ).strip()
    if decision_key == "approve" and recommendation_state != ADMISSION_RECOMMENDED_STATE:
        raise GovernedExecutionFailure(
            "cannot mark the candidate ready because admission is not currently recommended",
            summary_artifact_path=str(paths["baseline_admission_recommendation_path"]),
        )

    if decision_key == "approve":
        decision_state = BASELINE_CANDIDATE_READY_STATE
        admitted_candidate = True
        remediation_required = False
    elif decision_key == "defer":
        decision_state = ADMISSION_DEFERRED_STATE
        admitted_candidate = False
        remediation_required = bool(remediation_proposal.get("remediation_required", False))
    else:
        decision_state = REMEDIATION_REQUIRED_STATE
        admitted_candidate = False
        remediation_required = True

    if decision_key == "reject" and not str(remediation_proposal.get("objective_id", "")).strip():
        remediation_proposal = {
            "schema_name": SUCCESSOR_BASELINE_REMEDIATION_PROPOSAL_SCHEMA_NAME,
            "schema_version": SUCCESSOR_BASELINE_REMEDIATION_PROPOSAL_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": str(admission_review.get("directive_id", "")),
            "workspace_id": str(workspace_root_path.name),
            "workspace_root": str(workspace_root_path),
            "candidate_bundle_objective_id": str(candidate_bundle.get("objective_id", "")),
            "completed_objective_id": str(admission_review.get("completed_objective_id", "")),
            "completed_objective_source_kind": str(
                admission_review.get("completed_objective_source_kind", "")
            ),
            "proposal_state": REMEDIATION_REQUIRED_STATE,
            "remediation_required": True,
            "objective_id": "prepare_candidate_promotion_bundle",
            "objective_class": "prepare_candidate_promotion_bundle",
            "title": "Prepare a revised candidate promotion bundle",
            "rationale": "Operator review rejected admission for the current candidate, so a revised bounded candidate promotion bundle is proposed before another admission attempt.",
            "admission_recommendation_state": recommendation_state,
            "operator_review_required": True,
            "authorized_for_automatic_execution": False,
            "weak_areas": list(admission_recommendation.get("weak_areas", [])),
        }
        paths["baseline_remediation_proposal_path"].write_text(
            _dump(remediation_proposal),
            encoding="utf-8",
        )

    decision_payload = {
        "schema_name": SUCCESSOR_BASELINE_ADMISSION_DECISION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_BASELINE_ADMISSION_DECISION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(admission_review.get("directive_id", "")),
        "workspace_id": str(workspace_root_path.name),
        "workspace_root": str(workspace_root_path),
        "candidate_bundle_objective_id": str(admission_review.get("candidate_bundle_objective_id", "")),
        "candidate_bundle_identity": candidate_bundle_identity,
        "candidate_bundle_variant": candidate_bundle_variant,
        "candidate_bundle_manifest_path": candidate_bundle_manifest_path,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "revised_candidate_bundle_path": revised_candidate_bundle_path,
        "completed_objective_id": str(admission_review.get("completed_objective_id", "")),
        "completed_objective_source_kind": str(
            admission_review.get("completed_objective_source_kind", "")
        ),
        "admission_decision_state": decision_state,
        "operator_decision": decision_key,
        "operator_note": str(operator_note or "").strip(),
        "decision_actor": actor,
        "admission_recommendation_state": recommendation_state,
        "admission_recommended": bool(
            admission_recommendation.get("admission_recommended", False)
        ),
        "operator_review_required": not admitted_candidate,
        "admitted_bounded_baseline_candidate": admitted_candidate,
        "baseline_mutation_performed": False,
        "remediation_required": remediation_required,
        "review_path": str(paths["baseline_admission_review_path"]),
        "recommendation_path": str(paths["baseline_admission_recommendation_path"]),
        "remediation_proposal_path": str(paths["baseline_remediation_proposal_path"]),
        "candidate_materially_stronger_than_bounded_baseline": bool(
            admission_recommendation.get(
                "candidate_materially_stronger_than_bounded_baseline",
                admission_review.get(
                    "candidate_materially_stronger_than_bounded_baseline",
                    False,
                ),
            )
        ),
        "admitted_candidate_marker_state": (
            "admitted_bounded_baseline_candidate" if admitted_candidate else "not_admitted"
        ),
    }
    paths["baseline_admission_decision_path"].write_text(
        _dump(decision_payload),
        encoding="utf-8",
    )
    _sync_baseline_admission_decision_to_latest_artifacts(
        workspace_root=workspace_root_path,
        paths=paths,
        admission_review=admission_review,
        admission_recommendation=admission_recommendation,
        decision_payload=decision_payload,
        remediation_proposal=remediation_proposal,
    )
    candidate_lifecycle_outputs = _materialize_admitted_candidate_lifecycle_outputs(
        workspace_root=workspace_root_path,
        admission_review=admission_review,
        admission_recommendation=admission_recommendation,
        decision_payload=decision_payload,
        baseline_remediation_proposal=remediation_proposal,
    )
    paths["admitted_candidate_path"].write_text(
        _dump(dict(candidate_lifecycle_outputs.get("admitted_candidate", {}))),
        encoding="utf-8",
    )
    paths["admitted_candidate_handoff_path"].write_text(
        _dump(dict(candidate_lifecycle_outputs.get("admitted_candidate_handoff", {}))),
        encoding="utf-8",
    )
    paths["baseline_comparison_path"].write_text(
        _dump(dict(candidate_lifecycle_outputs.get("baseline_comparison", {}))),
        encoding="utf-8",
    )
    paths["reference_target_path"].write_text(
        _dump(dict(candidate_lifecycle_outputs.get("reference_target", {}))),
        encoding="utf-8",
    )
    paths["workspace_artifact_index_path"].write_text(
        _dump(dict(candidate_lifecycle_outputs.get("workspace_artifact_index", {}))),
        encoding="utf-8",
    )
    _sync_candidate_lifecycle_to_latest_artifacts(
        workspace_root=workspace_root_path,
        paths=paths,
        admitted_candidate=dict(candidate_lifecycle_outputs.get("admitted_candidate", {})),
        admitted_candidate_handoff=dict(
            candidate_lifecycle_outputs.get("admitted_candidate_handoff", {})
        ),
        baseline_comparison=dict(
            candidate_lifecycle_outputs.get("baseline_comparison", {})
        ),
        reference_target=dict(candidate_lifecycle_outputs.get("reference_target", {})),
    )
    revised_candidate_outputs = _update_revised_candidate_decision_artifacts(
        workspace_root=workspace_root_path,
        paths=paths,
        decision_payload=decision_payload,
        admitted_candidate_payload=dict(
            candidate_lifecycle_outputs.get("admitted_candidate", {})
        ),
        reference_target_payload=dict(
            candidate_lifecycle_outputs.get("reference_target", {})
        ),
    )

    session_summary = load_session_summary(workspace_root_path)
    runtime_event_log_path = Path(str(session_summary.get("runtime_event_log_path", "")).strip())
    session_id = str(session_summary.get("session_id", "")).strip() or "operator_review"
    directive_id = str(admission_review.get("directive_id", "")).strip()
    execution_profile = (
        str(session_summary.get("execution_profile", "")).strip()
        or "bounded_active_workspace_coding"
    )
    post_admission_quality_outputs: dict[str, Any] = {}
    generation_progress_outputs: dict[str, Any] = {}
    strategy_selection_outputs: dict[str, Any] = {}
    campaign_governance_outputs: dict[str, Any] = {}
    if admitted_candidate:
        current_directive = {
            "directive_id": directive_id,
            "active_branch": str(session_summary.get("active_branch", "")).strip(),
        }
        completed_objective_id = str(
            admission_review.get("completed_objective_id", "")
        ).strip() or str(admission_review.get("candidate_bundle_objective_id", "")).strip()
        current_objective = {
            "objective_id": completed_objective_id,
            "objective_class": _objective_class_from_objective_id(completed_objective_id),
            "source_kind": str(
                admission_review.get("completed_objective_source_kind", "")
            ).strip()
            or OBJECTIVE_SOURCE_APPROVED_RESEED,
            "title": str(candidate_bundle.get("objective_title", "")).strip()
            or str(candidate_bundle.get("objective_id", "")).strip()
            or _humanize_objective_id(completed_objective_id),
        }
        reference_target_consumption = _resolve_reference_target_consumption(
            current_directive=current_directive,
            workspace_root=workspace_root_path,
            current_objective=current_objective,
        )
        if str(runtime_event_log_path) not in {"", "."}:
            _write_json(
                paths["reference_target_consumption_path"],
                reference_target_consumption,
                log_path=runtime_event_log_path,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=str(workspace_root_path.name),
                workspace_root=str(workspace_root_path),
                work_item_id="successor_reference_target_consumption",
                artifact_kind="successor_reference_target_consumption_json",
            )
        else:
            paths["reference_target_consumption_path"].write_text(
                _dump(reference_target_consumption),
                encoding="utf-8",
            )

        quality_roadmap_outputs = _materialize_successor_quality_roadmap_outputs(
            workspace_root=workspace_root_path,
            current_objective=current_objective,
            reference_target_context=reference_target_consumption,
            latest_skill_pack_invocation=load_json(paths["skill_pack_invocation_path"]),
            latest_skill_pack_result=load_json(paths["skill_pack_result_path"]),
            latest_quality_gap_summary=load_json(paths["quality_gap_summary_path"]),
            latest_quality_improvement_summary=load_json(
                paths["quality_improvement_summary_path"]
            ),
            runtime_event_log_path=runtime_event_log_path
            if str(runtime_event_log_path) not in {"", "."}
            else None,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
        )
        next_pack_plan = dict(quality_roadmap_outputs.get("next_pack_plan", {}))
        promotion_recommendation = load_json(paths["promotion_recommendation_path"])
        next_objective_proposal: dict[str, Any] = {}
        selected_objective_id = str(
            next_pack_plan.get("selected_objective_id", "")
        ).strip()
        if (
            str(reference_target_consumption.get("consumption_state", "")).strip()
            == REFERENCE_TARGET_CONSUMED_STATE
            and selected_objective_id
        ):
            review_pack, _review_source = _load_internal_knowledge_pack(
                session=session_summary,
                source_id=INTERNAL_SUCCESSOR_PROMOTION_REVIEW_SOURCE_ID,
                expected_schema_name=SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_NAME,
                expected_schema_version=SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_VERSION,
            )
            template = dict(_objective_template_rows(review_pack).get(selected_objective_id, {}))
            next_objective_proposal = {
                "schema_name": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME,
                "schema_version": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION,
                "generated_at": _now(),
                "proposal_state": NEXT_OBJECTIVE_AVAILABLE_STATE,
                "proposal_source": "quality_roadmap_follow_on",
                "objective_id": selected_objective_id,
                "objective_class": _objective_class_from_objective_id(
                    selected_objective_id
                ),
                "title": str(template.get("title", "")).strip()
                or str(next_pack_plan.get("selected_objective_title", "")).strip()
                or _humanize_objective_id(selected_objective_id),
                "rationale": (
                    "Admission approval recorded the admitted candidate as the active bounded "
                    "reference target, and the successor-quality roadmap now recommends the next "
                    "highest-priority bounded quality-improvement dimension for explicit operator review. "
                    f"Selected dimension: {str(next_pack_plan.get('selected_dimension_title', '')).strip() or '<unknown>'}. "
                    f"Selected bounded skill pack: {str(next_pack_plan.get('selected_skill_pack_id', '')).strip() or '<unknown>'}. "
                    f"Active bounded reference target: `{str(reference_target_consumption.get('active_bounded_reference_target_id', '')).strip() or 'current_bounded_baseline_expectations_v1'}`."
                ),
                "promotion_recommendation_state": str(
                    promotion_recommendation.get("promotion_recommendation_state", "")
                ),
                "operator_review_required": True,
                "authorized_for_automatic_execution": False,
                "bounded_objective_complete": True,
                "quality_roadmap_path": str(paths["quality_roadmap_path"]),
                "quality_next_pack_plan_path": str(paths["quality_next_pack_plan_path"]),
                "selected_quality_dimension_id": str(
                    next_pack_plan.get("selected_dimension_id", "")
                ).strip(),
            }
            if str(runtime_event_log_path) not in {"", "."}:
                _write_json(
                    paths["next_objective_proposal_path"],
                    next_objective_proposal,
                    log_path=runtime_event_log_path,
                    session_id=session_id,
                    directive_id=directive_id,
                    execution_profile=execution_profile,
                    workspace_id=str(workspace_root_path.name),
                    workspace_root=str(workspace_root_path),
                    work_item_id="successor_quality_roadmap_follow_on",
                    artifact_kind="successor_next_objective_proposal_json",
                )
            else:
                paths["next_objective_proposal_path"].write_text(
                    _dump(next_objective_proposal),
                    encoding="utf-8",
                )

        reseed_outputs: dict[str, Any] = {}
        if next_objective_proposal:
            review_outputs = {
                "review_summary": load_json(paths["review_summary_path"]),
                "review_summary_path": str(paths["review_summary_path"]),
                "promotion_recommendation": promotion_recommendation,
                "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
                "next_objective_proposal": next_objective_proposal,
                "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
            }
            if str(runtime_event_log_path) not in {"", "."}:
                reseed_outputs = _materialize_successor_reseed_request_outputs(
                    current_directive=current_directive,
                    workspace_root=workspace_root_path,
                    review_outputs=review_outputs,
                    runtime_event_log_path=runtime_event_log_path,
                    session_id=session_id,
                    directive_id=directive_id,
                    execution_profile=execution_profile,
                    workspace_id=str(workspace_root_path.name),
                )
            else:
                reseed_outputs = _build_pending_reseed_outputs(
                    current_directive=current_directive,
                    workspace_root=workspace_root_path,
                    review_outputs=review_outputs,
                )
                paths["reseed_request_path"].write_text(
                    _dump(dict(reseed_outputs.get("request", {}))),
                    encoding="utf-8",
                )
                paths["reseed_decision_path"].write_text(
                    _dump(dict(reseed_outputs.get("decision", {}))),
                    encoding="utf-8",
                )
                paths["continuation_lineage_path"].write_text(
                    _dump(dict(reseed_outputs.get("continuation_lineage", {}))),
                    encoding="utf-8",
                )
                paths["effective_next_objective_path"].write_text(
                    _dump(dict(reseed_outputs.get("effective_next_objective", {}))),
                    encoding="utf-8",
                )

        _sync_post_admission_quality_follow_on_to_latest_artifacts(
            workspace_root=workspace_root_path,
            paths=paths,
            reference_target_consumption=reference_target_consumption,
            quality_roadmap_outputs=quality_roadmap_outputs,
            next_objective_proposal=next_objective_proposal,
            reseed_outputs=reseed_outputs,
        )
        generation_progress_outputs = _materialize_successor_generation_progress_outputs(
            workspace_root=workspace_root_path,
            runtime_event_log_path=runtime_event_log_path
            if str(runtime_event_log_path) not in {"", "."}
            else None,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
        )
        strategy_selection_outputs = _materialize_successor_strategy_selection_outputs(
            workspace_root=workspace_root_path,
            runtime_event_log_path=runtime_event_log_path
            if str(runtime_event_log_path) not in {"", "."}
            else None,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
        )
        strategy_follow_on_outputs = _materialize_successor_strategy_follow_on_handoff(
            current_directive=current_directive,
            workspace_root=workspace_root_path,
            session=session_summary,
            review_outputs={
                "review_summary": load_json(paths["review_summary_path"]),
                "review_summary_path": str(paths["review_summary_path"]),
                "promotion_recommendation": promotion_recommendation,
                "promotion_recommendation_path": str(
                    paths["promotion_recommendation_path"]
                ),
                "next_objective_proposal": next_objective_proposal,
                "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
            },
            reseed_outputs=reseed_outputs,
            strategy_selection_outputs=strategy_selection_outputs,
            runtime_event_log_path=runtime_event_log_path
            if str(runtime_event_log_path) not in {"", "."}
            else None,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
        )
        if bool(strategy_follow_on_outputs.get("strategy_follow_on_materialized", False)):
            next_objective_proposal = dict(
                strategy_follow_on_outputs.get("next_objective_proposal", {})
            )
            reseed_outputs = dict(
                strategy_follow_on_outputs.get("reseed_outputs", reseed_outputs)
            )
            _sync_post_admission_quality_follow_on_to_latest_artifacts(
                workspace_root=workspace_root_path,
                paths=paths,
                reference_target_consumption=reference_target_consumption,
                quality_roadmap_outputs=quality_roadmap_outputs,
                next_objective_proposal=next_objective_proposal,
                reseed_outputs=reseed_outputs,
            )
        campaign_governance_outputs = (
            _materialize_successor_campaign_governance_outputs(
                workspace_root=workspace_root_path,
                runtime_event_log_path=runtime_event_log_path
                if str(runtime_event_log_path) not in {"", "."}
                else None,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=str(workspace_root_path.name),
            )
        )
        campaign_follow_on_outputs = (
            _materialize_successor_campaign_follow_on_handoff(
                current_directive=current_directive,
                workspace_root=workspace_root_path,
                session=session_summary,
                review_outputs={
                    "review_summary": load_json(paths["review_summary_path"]),
                    "review_summary_path": str(paths["review_summary_path"]),
                    "promotion_recommendation": promotion_recommendation,
                    "promotion_recommendation_path": str(
                        paths["promotion_recommendation_path"]
                    ),
                    "next_objective_proposal": next_objective_proposal,
                    "next_objective_proposal_path": str(
                        paths["next_objective_proposal_path"]
                    ),
                },
                reseed_outputs=reseed_outputs,
                campaign_governance_outputs=campaign_governance_outputs,
                runtime_event_log_path=runtime_event_log_path
                if str(runtime_event_log_path) not in {"", "."}
                else None,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=str(workspace_root_path.name),
            )
        )
        if bool(campaign_follow_on_outputs.get("campaign_follow_on_materialized", False)):
            next_objective_proposal = dict(
                campaign_follow_on_outputs.get("next_objective_proposal", {})
            )
            reseed_outputs = dict(
                campaign_follow_on_outputs.get("reseed_outputs", reseed_outputs)
            )
            _sync_post_admission_quality_follow_on_to_latest_artifacts(
                workspace_root=workspace_root_path,
                paths=paths,
                reference_target_consumption=reference_target_consumption,
                quality_roadmap_outputs=quality_roadmap_outputs,
                next_objective_proposal=next_objective_proposal,
                reseed_outputs=reseed_outputs,
            )
        campaign_cycle_governance_outputs = (
            _materialize_successor_campaign_cycle_governance_outputs(
                workspace_root=workspace_root_path,
                runtime_event_log_path=runtime_event_log_path
                if str(runtime_event_log_path) not in {"", "."}
                else None,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=str(workspace_root_path.name),
            )
        )
        campaign_cycle_follow_on_outputs = (
            _materialize_successor_campaign_cycle_follow_on_handoff(
                current_directive=current_directive,
                workspace_root=workspace_root_path,
                session=session_summary,
                review_outputs={
                    "review_summary": load_json(paths["review_summary_path"]),
                    "review_summary_path": str(paths["review_summary_path"]),
                    "promotion_recommendation": promotion_recommendation,
                    "promotion_recommendation_path": str(
                        paths["promotion_recommendation_path"]
                    ),
                    "next_objective_proposal": next_objective_proposal,
                    "next_objective_proposal_path": str(
                        paths["next_objective_proposal_path"]
                    ),
                },
                reseed_outputs=reseed_outputs,
                campaign_cycle_governance_outputs=campaign_cycle_governance_outputs,
                runtime_event_log_path=runtime_event_log_path
                if str(runtime_event_log_path) not in {"", "."}
                else None,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=str(workspace_root_path.name),
            )
        )
        if bool(
            campaign_cycle_follow_on_outputs.get(
                "campaign_cycle_follow_on_materialized", False
            )
        ):
            next_objective_proposal = dict(
                campaign_cycle_follow_on_outputs.get("next_objective_proposal", {})
            )
            reseed_outputs = dict(
                campaign_cycle_follow_on_outputs.get(
                    "reseed_outputs", reseed_outputs
                )
            )
            _sync_post_admission_quality_follow_on_to_latest_artifacts(
                workspace_root=workspace_root_path,
                paths=paths,
                reference_target_consumption=reference_target_consumption,
                quality_roadmap_outputs=quality_roadmap_outputs,
                next_objective_proposal=next_objective_proposal,
                reseed_outputs=reseed_outputs,
            )
        loop_governance_outputs = _materialize_successor_loop_governance_outputs(
            workspace_root=workspace_root_path,
            runtime_event_log_path=runtime_event_log_path
            if str(runtime_event_log_path) not in {"", "."}
            else None,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
        )
        post_admission_quality_outputs = {
            "reference_target_consumption": reference_target_consumption,
            "reference_target_consumption_path": str(
                paths["reference_target_consumption_path"]
            ),
            "quality_roadmap_outputs": quality_roadmap_outputs,
            "next_objective_proposal": next_objective_proposal,
            "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
            "reseed_outputs": reseed_outputs,
            "campaign_governance_outputs": campaign_governance_outputs,
            "campaign_cycle_governance_outputs": campaign_cycle_governance_outputs,
            "loop_governance_outputs": loop_governance_outputs,
        }
    if str(runtime_event_log_path):
        _event(
            runtime_event_log_path,
            event_type="successor_baseline_admission_decision_recorded",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
            workspace_root=str(workspace_root_path),
            admission_decision_state=decision_state,
            operator_decision=decision_key,
            admitted_bounded_baseline_candidate=admitted_candidate,
            remediation_required=remediation_required,
            admission_decision_path=str(paths["baseline_admission_decision_path"]),
            remediation_proposal_path=str(paths["baseline_remediation_proposal_path"]),
        )
        _event(
            runtime_event_log_path,
            event_type="successor_admitted_candidate_recorded",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
            workspace_root=str(workspace_root_path),
            admission_decision_state=decision_state,
            admitted_candidate_state=str(
                dict(candidate_lifecycle_outputs.get("admitted_candidate", {})).get(
                    "admitted_candidate_state", ""
                )
            ),
            admitted_bounded_baseline_candidate=admitted_candidate,
            admitted_candidate_path=str(paths["admitted_candidate_path"]),
            handoff_path=str(paths["admitted_candidate_handoff_path"]),
        )
        _event(
            runtime_event_log_path,
            event_type="successor_baseline_comparison_completed",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
            workspace_root=str(workspace_root_path),
            admission_decision_state=decision_state,
            stronger_than_current_bounded_baseline=bool(
                dict(candidate_lifecycle_outputs.get("baseline_comparison", {})).get(
                    "stronger_than_current_bounded_baseline", False
                )
            ),
            future_reference_target_state=str(
                dict(candidate_lifecycle_outputs.get("reference_target", {})).get(
                    "reference_target_state", ""
                )
            ),
            remediation_objective_id=str(
                dict(
                    dict(candidate_lifecycle_outputs.get("baseline_comparison", {})).get(
                        "remediation_proposal", {}
                    )
                ).get("objective_id", "")
            ),
            comparison_path=str(paths["baseline_comparison_path"]),
            reason=str(
                dict(candidate_lifecycle_outputs.get("baseline_comparison", {})).get(
                    "comparison_rationale", ""
                )
            ),
        )
        _event(
            runtime_event_log_path,
            event_type="successor_reference_target_recorded",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
            workspace_root=str(workspace_root_path),
            reference_target_state=str(
                dict(candidate_lifecycle_outputs.get("reference_target", {})).get(
                    "reference_target_state", ""
                )
            ),
            future_reference_target_eligible=bool(
                dict(candidate_lifecycle_outputs.get("reference_target", {})).get(
                    "eligible_as_future_reference_target", False
                )
            ),
            preferred_reference_target_id=str(
                dict(candidate_lifecycle_outputs.get("reference_target", {})).get(
                    "preferred_reference_target_id", ""
                )
            ),
            reference_target_path=str(paths["reference_target_path"]),
            reason=str(
                dict(candidate_lifecycle_outputs.get("reference_target", {})).get(
                    "reference_target_rationale", ""
                )
            ),
        )
    return {
        "decision": decision_payload,
        "decision_path": str(paths["baseline_admission_decision_path"]),
        "remediation_proposal": remediation_proposal,
        "remediation_proposal_path": str(paths["baseline_remediation_proposal_path"]),
        "admitted_candidate": dict(candidate_lifecycle_outputs.get("admitted_candidate", {})),
        "admitted_candidate_path": str(paths["admitted_candidate_path"]),
        "admitted_candidate_handoff": dict(
            candidate_lifecycle_outputs.get("admitted_candidate_handoff", {})
        ),
        "admitted_candidate_handoff_path": str(paths["admitted_candidate_handoff_path"]),
        "baseline_comparison": dict(
            candidate_lifecycle_outputs.get("baseline_comparison", {})
        ),
        "baseline_comparison_path": str(paths["baseline_comparison_path"]),
        "reference_target": dict(candidate_lifecycle_outputs.get("reference_target", {})),
        "reference_target_path": str(paths["reference_target_path"]),
        "revised_candidate_bundle": dict(
            revised_candidate_outputs.get("revised_candidate_bundle", {})
        ),
        "revised_candidate_bundle_path": str(
            revised_candidate_outputs.get("revised_candidate_bundle_path", "")
        ),
        "revised_candidate_handoff": dict(
            revised_candidate_outputs.get("revised_candidate_handoff", {})
        ),
        "revised_candidate_handoff_path": str(
            revised_candidate_outputs.get("revised_candidate_handoff_path", "")
        ),
        "revised_candidate_comparison": dict(
            revised_candidate_outputs.get("revised_candidate_comparison", {})
        ),
        "revised_candidate_comparison_path": str(
            revised_candidate_outputs.get("revised_candidate_comparison_path", "")
        ),
        "revised_candidate_promotion_summary": dict(
            revised_candidate_outputs.get("revised_candidate_promotion_summary", {})
        ),
        "revised_candidate_promotion_summary_path": str(
            revised_candidate_outputs.get("revised_candidate_promotion_summary_path", "")
        ),
        "reference_target_consumption": dict(
            post_admission_quality_outputs.get("reference_target_consumption", {})
        ),
        "reference_target_consumption_path": str(
            post_admission_quality_outputs.get("reference_target_consumption_path", "")
        ),
        "quality_roadmap_outputs": dict(
            post_admission_quality_outputs.get("quality_roadmap_outputs", {})
        ),
        "next_objective_proposal": dict(
            post_admission_quality_outputs.get("next_objective_proposal", {})
        ),
        "next_objective_proposal_path": str(
            post_admission_quality_outputs.get("next_objective_proposal_path", "")
        ),
        "reseed_outputs": dict(post_admission_quality_outputs.get("reseed_outputs", {})),
        "generation_history": dict(
            generation_progress_outputs.get("generation_history", {})
        ),
        "generation_history_path": str(
            generation_progress_outputs.get("generation_history_path", "")
        ),
        "generation_delta": dict(
            generation_progress_outputs.get("generation_delta", {})
        ),
        "generation_delta_path": str(
            generation_progress_outputs.get("generation_delta_path", "")
        ),
        "progress_governance": dict(
            generation_progress_outputs.get("progress_governance", {})
        ),
        "progress_governance_path": str(
            generation_progress_outputs.get("progress_governance_path", "")
        ),
        "progress_recommendation": dict(
            generation_progress_outputs.get("progress_recommendation", {})
        ),
        "progress_recommendation_path": str(
            generation_progress_outputs.get("progress_recommendation_path", "")
        ),
        "strategy_selection": dict(
            strategy_selection_outputs.get("strategy_selection", {})
        ),
        "strategy_selection_path": str(
            strategy_selection_outputs.get("strategy_selection_path", "")
        ),
        "strategy_rationale": dict(
            strategy_selection_outputs.get("strategy_rationale", {})
        ),
        "strategy_rationale_path": str(
            strategy_selection_outputs.get("strategy_rationale_path", "")
        ),
        "strategy_follow_on_plan": dict(
            strategy_selection_outputs.get("strategy_follow_on_plan", {})
        ),
        "strategy_follow_on_plan_path": str(
            strategy_selection_outputs.get("strategy_follow_on_plan_path", "")
        ),
        "strategy_decision_support": dict(
            strategy_selection_outputs.get("strategy_decision_support", {})
        ),
        "strategy_decision_support_path": str(
            strategy_selection_outputs.get("strategy_decision_support_path", "")
        ),
        "campaign_history": dict(campaign_governance_outputs.get("campaign_history", {})),
        "campaign_history_path": str(
            campaign_governance_outputs.get("campaign_history_path", "")
        ),
        "campaign_delta": dict(campaign_governance_outputs.get("campaign_delta", {})),
        "campaign_delta_path": str(
            campaign_governance_outputs.get("campaign_delta_path", "")
        ),
        "campaign_governance": dict(
            campaign_governance_outputs.get("campaign_governance", {})
        ),
        "campaign_governance_path": str(
            campaign_governance_outputs.get("campaign_governance_path", "")
        ),
        "campaign_recommendation": dict(
            campaign_governance_outputs.get("campaign_recommendation", {})
        ),
        "campaign_recommendation_path": str(
            campaign_governance_outputs.get("campaign_recommendation_path", "")
        ),
        "campaign_wave_plan": dict(
            campaign_governance_outputs.get("campaign_wave_plan", {})
        ),
        "campaign_wave_plan_path": str(
            campaign_governance_outputs.get("campaign_wave_plan_path", "")
        ),
        "campaign_cycle_history": dict(
            post_admission_quality_outputs.get("campaign_cycle_governance_outputs", {}).get(
                "campaign_cycle_history",
                {},
            )
        ),
        "campaign_cycle_history_path": str(
            post_admission_quality_outputs.get("campaign_cycle_governance_outputs", {}).get(
                "campaign_cycle_history_path",
                "",
            )
        ),
        "campaign_cycle_delta": dict(
            post_admission_quality_outputs.get("campaign_cycle_governance_outputs", {}).get(
                "campaign_cycle_delta",
                {},
            )
        ),
        "campaign_cycle_delta_path": str(
            post_admission_quality_outputs.get("campaign_cycle_governance_outputs", {}).get(
                "campaign_cycle_delta_path",
                "",
            )
        ),
        "campaign_cycle_governance": dict(
            post_admission_quality_outputs.get("campaign_cycle_governance_outputs", {}).get(
                "campaign_cycle_governance",
                {},
            )
        ),
        "campaign_cycle_governance_path": str(
            post_admission_quality_outputs.get("campaign_cycle_governance_outputs", {}).get(
                "campaign_cycle_governance_path",
                "",
            )
        ),
        "campaign_cycle_recommendation": dict(
            post_admission_quality_outputs.get("campaign_cycle_governance_outputs", {}).get(
                "campaign_cycle_recommendation",
                {},
            )
        ),
        "campaign_cycle_recommendation_path": str(
            post_admission_quality_outputs.get("campaign_cycle_governance_outputs", {}).get(
                "campaign_cycle_recommendation_path",
                "",
            )
        ),
        "campaign_cycle_follow_on_plan": dict(
            post_admission_quality_outputs.get("campaign_cycle_governance_outputs", {}).get(
                "campaign_cycle_follow_on_plan",
                {},
            )
        ),
        "campaign_cycle_follow_on_plan_path": str(
            post_admission_quality_outputs.get("campaign_cycle_governance_outputs", {}).get(
                "campaign_cycle_follow_on_plan_path",
                "",
            )
        ),
        "loop_history": dict(
            post_admission_quality_outputs.get("loop_governance_outputs", {}).get(
                "loop_history",
                {},
            )
        ),
        "loop_history_path": str(
            post_admission_quality_outputs.get("loop_governance_outputs", {}).get(
                "loop_history_path",
                "",
            )
        ),
        "loop_delta": dict(
            post_admission_quality_outputs.get("loop_governance_outputs", {}).get(
                "loop_delta",
                {},
            )
        ),
        "loop_delta_path": str(
            post_admission_quality_outputs.get("loop_governance_outputs", {}).get(
                "loop_delta_path",
                "",
            )
        ),
        "loop_governance": dict(
            post_admission_quality_outputs.get("loop_governance_outputs", {}).get(
                "loop_governance",
                {},
            )
        ),
        "loop_governance_path": str(
            post_admission_quality_outputs.get("loop_governance_outputs", {}).get(
                "loop_governance_path",
                "",
            )
        ),
        "loop_recommendation": dict(
            post_admission_quality_outputs.get("loop_governance_outputs", {}).get(
                "loop_recommendation",
                {},
            )
        ),
        "loop_recommendation_path": str(
            post_admission_quality_outputs.get("loop_governance_outputs", {}).get(
                "loop_recommendation_path",
                "",
            )
        ),
        "loop_follow_on_plan": dict(
            post_admission_quality_outputs.get("loop_governance_outputs", {}).get(
                "loop_follow_on_plan",
                {},
            )
        ),
        "loop_follow_on_plan_path": str(
            post_admission_quality_outputs.get("loop_governance_outputs", {}).get(
                "loop_follow_on_plan_path",
                "",
            )
        ),
    }


def _build_pending_reseed_outputs(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    review_outputs: dict[str, Any],
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    review_summary = dict(review_outputs.get("review_summary", {}))
    promotion_recommendation = dict(review_outputs.get("promotion_recommendation", {}))
    next_objective_proposal = dict(review_outputs.get("next_objective_proposal", {}))
    completed_objective_id = str(review_summary.get("completed_objective_id", "")).strip() or str(
        current_directive.get("directive_id", "")
    ).strip()
    completed_objective_source_kind = str(
        review_summary.get("completed_objective_source_kind", OBJECTIVE_SOURCE_DIRECTIVE)
    ).strip() or OBJECTIVE_SOURCE_DIRECTIVE
    proposed_objective_id = str(next_objective_proposal.get("objective_id", "")).strip()
    proposed_objective_class = _objective_class_from_objective_id(proposed_objective_id)
    reseed_state = RESEED_PENDING_REVIEW_STATE if proposed_objective_id else RESEED_DEFERRED_STATE
    request_rationale = (
        "A reviewed bounded next objective is available and awaits explicit operator approval before continuation."
        if proposed_objective_id
        else "No executable next bounded objective is proposed automatically in this slice; operator review remains required."
    )
    request_payload = {
        "schema_name": SUCCESSOR_RESEED_REQUEST_SCHEMA_NAME,
        "schema_version": SUCCESSOR_RESEED_REQUEST_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "review_summary_path": str(review_outputs.get("review_summary_path", "")),
        "promotion_recommendation_path": str(
            review_outputs.get("promotion_recommendation_path", "")
        ),
        "next_objective_proposal_path": str(review_outputs.get("next_objective_proposal_path", "")),
        "review_status": str(review_summary.get("review_status", "")),
        "promotion_recommendation_state": str(
            promotion_recommendation.get("promotion_recommendation_state", "")
        ),
        "proposal_state": str(next_objective_proposal.get("proposal_state", "")),
        "proposed_objective_id": proposed_objective_id,
        "proposed_objective_class": proposed_objective_class,
        "proposed_objective_title": str(next_objective_proposal.get("title", "")),
        "reseed_state": reseed_state,
        "operator_review_required": True,
        "continuation_authorized": False,
        "rationale": request_rationale,
    }
    decision_payload = {
        "schema_name": SUCCESSOR_RESEED_DECISION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_RESEED_DECISION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "reseed_state": reseed_state,
        "operator_decision": "pending_review",
        "operator_note": "",
        "continuation_authorized": False,
        "proposed_objective_id": proposed_objective_id,
        "proposed_objective_class": proposed_objective_class,
        "proposed_objective_title": str(next_objective_proposal.get("title", "")),
        "reseed_request_path": str(paths["reseed_request_path"]),
    }
    effective_payload = {
        "schema_name": SUCCESSOR_EFFECTIVE_NEXT_OBJECTIVE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_EFFECTIVE_NEXT_OBJECTIVE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "reseed_state": reseed_state,
        "continuation_authorized": False,
        "authorized_for_execution": False,
        "execution_state": "awaiting_operator_review" if proposed_objective_id else "no_authorized_continuation",
        "objective_id": "",
        "objective_class": "",
        "title": "",
        "rationale": request_rationale,
        "authorization_origin": "",
        "reseed_request_path": str(paths["reseed_request_path"]),
        "reseed_decision_path": str(paths["reseed_decision_path"]),
        "review_summary_path": str(review_outputs.get("review_summary_path", "")),
        "promotion_recommendation_path": str(
            review_outputs.get("promotion_recommendation_path", "")
        ),
        "next_objective_proposal_path": str(review_outputs.get("next_objective_proposal_path", "")),
    }
    lineage_payload = {
        "schema_name": SUCCESSOR_CONTINUATION_LINEAGE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_CONTINUATION_LINEAGE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "review_summary_path": str(review_outputs.get("review_summary_path", "")),
        "promotion_recommendation_path": str(
            review_outputs.get("promotion_recommendation_path", "")
        ),
        "next_objective_proposal_path": str(review_outputs.get("next_objective_proposal_path", "")),
        "reseed_request_path": str(paths["reseed_request_path"]),
        "reseed_decision_path": str(paths["reseed_decision_path"]),
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        "reseed_state": reseed_state,
        "operator_decision": "pending_review",
        "continuation_authorized": False,
        "proposed_objective_id": proposed_objective_id,
        "proposed_objective_class": proposed_objective_class,
        "proposed_objective_title": str(next_objective_proposal.get("title", "")),
        "effective_objective_id": "",
        "effective_objective_class": "",
        "authorization_origin": "",
    }
    return {
        "request": request_payload,
        "decision": decision_payload,
        "effective_next_objective": effective_payload,
        "continuation_lineage": lineage_payload,
        "reseed_request_path": str(paths["reseed_request_path"]),
        "reseed_decision_path": str(paths["reseed_decision_path"]),
        "continuation_lineage_path": str(paths["continuation_lineage_path"]),
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
    }


def _materialize_successor_reseed_request_outputs(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    review_outputs: dict[str, Any],
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    payloads = _build_pending_reseed_outputs(
        current_directive=current_directive,
        workspace_root=workspace_root,
        review_outputs=review_outputs,
    )
    write_rows = [
        (paths["reseed_request_path"], dict(payloads.get("request", {})), "successor_reseed_request_json"),
        (paths["reseed_decision_path"], dict(payloads.get("decision", {})), "successor_reseed_decision_json"),
        (
            paths["continuation_lineage_path"],
            dict(payloads.get("continuation_lineage", {})),
            "successor_continuation_lineage_json",
        ),
        (
            paths["effective_next_objective_path"],
            dict(payloads.get("effective_next_objective", {})),
            "successor_effective_next_objective_json",
        ),
    ]
    for artifact_path, artifact_payload, artifact_kind in write_rows:
        _write_json(
            artifact_path,
            artifact_payload,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id="successor_reseed_request",
            artifact_kind=artifact_kind,
        )
    _event(
        runtime_event_log_path,
        event_type="successor_reseed_request_materialized",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        reseed_state=str(dict(payloads.get("request", {})).get("reseed_state", "")),
        proposed_objective_id=str(dict(payloads.get("request", {})).get("proposed_objective_id", "")),
        reseed_request_path=str(paths["reseed_request_path"]),
    )
    return payloads


def materialize_successor_reseed_decision(
    *,
    workspace_root: str | Path,
    operator_decision: str,
    operator_note: str = "",
    actor: str = "operator_web_ui",
    operator_root: str | Path | None = None,
) -> dict[str, Any]:
    workspace_root_path = Path(workspace_root)
    paths = _workspace_paths(workspace_root_path)
    review_summary = load_json(paths["review_summary_path"])
    promotion_recommendation = load_json(paths["promotion_recommendation_path"])
    next_objective_proposal = load_json(paths["next_objective_proposal_path"])
    if not review_summary or not next_objective_proposal:
        raise GovernedExecutionFailure(
            "reseed decision requires existing review and next-objective proposal artifacts",
            summary_artifact_path=str(paths["review_summary_path"]),
        )
    decision_key = str(operator_decision or "").strip().lower()
    if decision_key not in {"approve", "reject", "defer", "auto_continue"}:
        raise GovernedExecutionFailure(
            "unsupported reseed decision; expected approve, reject, defer, or auto_continue"
        )
    proposed_objective_id = str(next_objective_proposal.get("objective_id", "")).strip()
    proposed_objective_class = _objective_class_from_objective_id(proposed_objective_id)
    if decision_key in {"approve", "auto_continue"} and not proposed_objective_id:
        raise GovernedExecutionFailure(
            "cannot approve continuation because no bounded next objective is currently proposed"
        )

    request_outputs = _build_pending_reseed_outputs(
        current_directive={"directive_id": str(review_summary.get("directive_id", ""))},
        workspace_root=workspace_root_path,
        review_outputs={
            "review_summary": review_summary,
            "promotion_recommendation": promotion_recommendation,
            "next_objective_proposal": next_objective_proposal,
            "review_summary_path": str(paths["review_summary_path"]),
            "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
            "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
        },
    )
    request_payload = dict(request_outputs.get("request", {}))
    completed_objective_id = str(request_payload.get("completed_objective_id", "")).strip()
    completed_objective_source_kind = str(
        request_payload.get("completed_objective_source_kind", OBJECTIVE_SOURCE_DIRECTIVE)
    ).strip() or OBJECTIVE_SOURCE_DIRECTIVE

    reseed_state = {
        "approve": RESEED_APPROVED_STATE,
        "reject": RESEED_REJECTED_STATE,
        "defer": RESEED_DEFERRED_STATE,
        "auto_continue": RESEED_APPROVED_STATE,
    }[decision_key]
    continuation_authorized = decision_key in {"approve", "auto_continue"}
    effective_state = RESEED_MATERIALIZED_STATE if continuation_authorized else reseed_state
    effective_objective_id = proposed_objective_id if continuation_authorized else ""
    effective_objective_class = (
        proposed_objective_class if continuation_authorized else ""
    )
    effective_title = (
        str(next_objective_proposal.get("title", "")).strip() if continuation_authorized else ""
    )
    effective_rationale = (
        str(next_objective_proposal.get("rationale", "")).strip()
        if continuation_authorized
        else f"Operator decision recorded as {decision_key}; no executable next objective is active."
    )
    authorization_origin = (
        AUTO_CONTINUE_ORIGIN_POLICY
        if decision_key == "auto_continue"
        else (AUTO_CONTINUE_ORIGIN_MANUAL if continuation_authorized else "")
    )
    decision_payload = {
        "schema_name": SUCCESSOR_RESEED_DECISION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_RESEED_DECISION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(review_summary.get("directive_id", "")),
        "workspace_id": str(workspace_root_path.name),
        "workspace_root": str(workspace_root_path),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "reseed_state": reseed_state,
        "operator_decision": decision_key,
        "operator_note": str(operator_note or "").strip(),
        "decision_actor": actor,
        "continuation_authorized": continuation_authorized,
        "proposed_objective_id": proposed_objective_id,
        "proposed_objective_class": proposed_objective_class,
        "proposed_objective_title": str(next_objective_proposal.get("title", "")),
        "authorization_origin": authorization_origin,
        "reseed_request_path": str(paths["reseed_request_path"]),
    }
    effective_payload = {
        "schema_name": SUCCESSOR_EFFECTIVE_NEXT_OBJECTIVE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_EFFECTIVE_NEXT_OBJECTIVE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(review_summary.get("directive_id", "")),
        "workspace_id": str(workspace_root_path.name),
        "workspace_root": str(workspace_root_path),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "reseed_state": effective_state,
        "continuation_authorized": continuation_authorized,
        "authorized_for_execution": continuation_authorized,
        "execution_state": "approved_pending_execution" if continuation_authorized else "not_authorized",
        "objective_id": effective_objective_id,
        "objective_class": effective_objective_class,
        "title": effective_title,
        "rationale": effective_rationale,
        "operator_decision": decision_key,
        "operator_note": str(operator_note or "").strip(),
        "authorization_origin": authorization_origin,
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
        "reseed_request_path": str(paths["reseed_request_path"]),
        "reseed_decision_path": str(paths["reseed_decision_path"]),
        "continuation_lineage_path": str(paths["continuation_lineage_path"]),
    }
    lineage_payload = {
        "schema_name": SUCCESSOR_CONTINUATION_LINEAGE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_CONTINUATION_LINEAGE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(review_summary.get("directive_id", "")),
        "workspace_id": str(workspace_root_path.name),
        "workspace_root": str(workspace_root_path),
        "completed_objective_id": completed_objective_id,
        "completed_objective_source_kind": completed_objective_source_kind,
        "review_summary_path": str(paths["review_summary_path"]),
        "promotion_recommendation_path": str(paths["promotion_recommendation_path"]),
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
        "reseed_request_path": str(paths["reseed_request_path"]),
        "reseed_decision_path": str(paths["reseed_decision_path"]),
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        "reseed_state": effective_state,
        "operator_decision": decision_key,
        "continuation_authorized": continuation_authorized,
        "proposed_objective_id": proposed_objective_id,
        "proposed_objective_class": proposed_objective_class,
        "effective_objective_id": effective_objective_id,
        "effective_objective_class": effective_objective_class,
        "effective_objective_title": effective_title,
        "authorization_origin": authorization_origin,
    }
    request_payload["generated_at"] = _now()
    request_payload["reseed_state"] = effective_state if continuation_authorized else reseed_state
    request_payload["operator_decision"] = decision_key
    request_payload["operator_note"] = str(operator_note or "").strip()
    request_payload["continuation_authorized"] = continuation_authorized
    request_payload["effective_objective_id"] = effective_objective_id
    request_payload["proposed_objective_class"] = proposed_objective_class
    request_payload["effective_objective_class"] = effective_objective_class
    request_payload["authorization_origin"] = authorization_origin

    for artifact_path, artifact_payload in (
        (paths["reseed_request_path"], request_payload),
        (paths["reseed_decision_path"], decision_payload),
        (paths["effective_next_objective_path"], effective_payload),
        (paths["continuation_lineage_path"], lineage_payload),
    ):
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    session_summary = load_session_summary(workspace_root_path)
    runtime_event_log_path = Path(str(session_summary.get("runtime_event_log_path", "")).strip())
    session_id = str(session_summary.get("session_id", "")).strip() or "operator_review"
    directive_id = str(review_summary.get("directive_id", "")).strip()
    execution_profile = str(session_summary.get("execution_profile", "")).strip() or "bounded_active_workspace_coding"
    auto_continue_outputs: dict[str, Any] = {
        "state": load_successor_auto_continue_state(workspace_root_path),
        "decision": load_successor_auto_continue_decision(workspace_root_path),
        "state_path": str(paths["auto_continue_state_path"]),
        "decision_path": str(paths["auto_continue_decision_path"]),
    }
    if decision_key != "auto_continue":
        auto_continue_outputs = _write_successor_auto_continue_state_and_decision(
            workspace_root=workspace_root_path,
            operator_root=operator_root,
            review_summary=review_summary,
            promotion_recommendation=promotion_recommendation,
            next_objective_proposal=next_objective_proposal,
            reseed_request_path=str(paths["reseed_request_path"]),
            reseed_decision_path=str(paths["reseed_decision_path"]),
            continuation_lineage_path=str(paths["continuation_lineage_path"]),
            effective_next_objective_path=str(paths["effective_next_objective_path"]),
            continuation_authorized=continuation_authorized,
            decision_reason={
                "approve": "manual_approval_recorded",
                "reject": "manual_reject_recorded",
                "defer": "manual_defer_recorded",
            }[decision_key],
            decision_actor=actor,
            authorization_origin=authorization_origin,
            operator_decision=decision_key,
            effective_objective_id=effective_objective_id,
            effective_objective_title=effective_title,
        )
    if str(runtime_event_log_path):
        _event(
            runtime_event_log_path,
            event_type="successor_reseed_decision_recorded",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
            workspace_root=str(workspace_root_path),
            reseed_state=reseed_state,
            operator_decision=decision_key,
            continuation_authorized=continuation_authorized,
            proposed_objective_id=proposed_objective_id,
            objective_class=proposed_objective_class,
            authorization_origin=authorization_origin,
            reseed_decision_path=str(paths["reseed_decision_path"]),
        )
        _event(
            runtime_event_log_path,
            event_type="successor_effective_next_objective_materialized",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=str(workspace_root_path.name),
            workspace_root=str(workspace_root_path),
            reseed_state=effective_state,
            continuation_authorized=continuation_authorized,
            effective_objective_id=effective_objective_id,
            objective_class=effective_objective_class,
            authorization_origin=authorization_origin,
            effective_next_objective_path=str(paths["effective_next_objective_path"]),
        )
    return {
        "request": request_payload,
        "decision": decision_payload,
        "effective_next_objective": effective_payload,
        "continuation_lineage": lineage_payload,
        "auto_continue_state": dict(auto_continue_outputs.get("state", {})),
        "auto_continue_decision": dict(auto_continue_outputs.get("decision", {})),
        "reseed_request_path": str(paths["reseed_request_path"]),
        "reseed_decision_path": str(paths["reseed_decision_path"]),
        "continuation_lineage_path": str(paths["continuation_lineage_path"]),
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        "auto_continue_state_path": str(paths["auto_continue_state_path"]),
        "auto_continue_decision_path": str(paths["auto_continue_decision_path"]),
    }


def _update_effective_next_objective_after_run(
    *,
    workspace_root: Path,
    current_objective: dict[str, Any],
    completion_evaluation: dict[str, Any],
    stop_reason: str,
    stop_detail: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    payload = load_json(paths["effective_next_objective_path"])
    if not payload:
        return {}
    if (
        str(current_objective.get("source_kind", "")).strip() != OBJECTIVE_SOURCE_APPROVED_RESEED
        or str(payload.get("objective_id", "")).strip()
        != str(current_objective.get("objective_id", "")).strip()
    ):
        return payload
    updated = dict(payload)
    updated["generated_at"] = _now()
    updated["last_stop_reason"] = str(stop_reason)
    updated["last_stop_detail"] = str(stop_detail)
    latest_skill_pack_result = load_json(paths["skill_pack_result_path"])
    latest_quality_improvement_summary = load_json(
        paths["quality_improvement_summary_path"]
    )
    quality_step_completed = (
        str(current_objective.get("objective_class", "")).strip()
        in SUCCESSOR_SKILL_PACKS_BY_OBJECTIVE_CLASS
        and str(latest_skill_pack_result.get("result_state", "")).strip() == "complete"
        and str(latest_quality_improvement_summary.get("improvement_state", "")).strip()
        == "complete"
    )
    if bool(completion_evaluation.get("completed", False)):
        updated["execution_state"] = "completed"
        updated["completed_at"] = _now()
        updated["continuation_authorized"] = False
        updated["authorized_for_execution"] = False
    elif stop_reason in {STOP_REASON_SINGLE_CYCLE, STOP_REASON_MAX_CAP}:
        updated["execution_state"] = (
            QUALITY_CHAIN_REENTRY_READY_STATE
            if quality_step_completed
            else "awaiting_additional_reentry"
        )
    elif stop_reason in {STOP_REASON_FAILURE, STOP_REASON_NO_WORK, STOP_REASON_BLOCKED}:
        updated["execution_state"] = "execution_blocked"
    paths["effective_next_objective_path"].write_text(_dump(updated), encoding="utf-8")
    lineage_payload = load_json(paths["continuation_lineage_path"])
    if lineage_payload:
        lineage_payload["generated_at"] = _now()
        lineage_payload["effective_objective_id"] = str(updated.get("objective_id", ""))
        lineage_payload["effective_objective_execution_state"] = str(
            updated.get("execution_state", "")
        )
        lineage_payload["continuation_authorized"] = bool(
            updated.get("continuation_authorized", False)
        )
        lineage_payload["last_stop_reason"] = str(stop_reason)
        lineage_payload["last_stop_detail"] = str(stop_detail)
        paths["continuation_lineage_path"].write_text(_dump(lineage_payload), encoding="utf-8")
    return updated


def _materialize_successor_quality_chain_reentry(
    *,
    workspace_root: Path,
    current_objective: dict[str, Any],
    completion_evaluation: dict[str, Any],
    review_outputs: dict[str, Any],
    reseed_outputs: dict[str, Any],
    auto_continue_outputs: dict[str, Any],
    stop_reason: str,
    stop_detail: str,
    remaining_counted_cycle_budget: int,
    budget_staging_decision: str,
    budget_staging_rationale: str,
    auto_continue_transition_state: str,
    runtime_event_log_path: Path | str | None = None,
    session_id: str = "",
    directive_id: str = "",
    execution_profile: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    skill_pack_invocation = load_json(paths["skill_pack_invocation_path"])
    skill_pack_result = load_json(paths["skill_pack_result_path"])
    quality_gap_summary = load_json(paths["quality_gap_summary_path"])
    quality_improvement_summary = load_json(paths["quality_improvement_summary_path"])
    next_objective_proposal = dict(review_outputs.get("next_objective_proposal", {}))
    effective_next_objective = dict(reseed_outputs.get("effective_next_objective", {}))
    current_source_kind = str(current_objective.get("source_kind", "")).strip()
    current_objective_id = str(current_objective.get("objective_id", "")).strip()
    current_objective_class = str(current_objective.get("objective_class", "")).strip()
    next_objective_id = str(next_objective_proposal.get("objective_id", "")).strip()
    next_objective_class = str(next_objective_proposal.get("objective_class", "")).strip()
    selected_skill_pack_id = str(skill_pack_invocation.get("selected_skill_pack_id", "")).strip()
    skill_pack_completed = (
        str(skill_pack_result.get("result_state", "")).strip() == "complete"
        and str(quality_improvement_summary.get("improvement_state", "")).strip()
        == "complete"
    )
    compact_follow_on = _is_compact_auto_continue_objective(next_objective_class)
    reentry_state = QUALITY_CHAIN_REENTRY_NOT_APPLICABLE_STATE
    reentry_reason = ""
    recommended_action = "no_immediate_reentry_required"
    if current_source_kind == OBJECTIVE_SOURCE_APPROVED_RESEED and (
        current_objective_class in SUCCESSOR_SKILL_PACKS_BY_OBJECTIVE_CLASS
        or selected_skill_pack_id
    ):
        if str(auto_continue_transition_state).strip() == AUTO_CONTINUE_TRANSITION_STARTED:
            reentry_state = QUALITY_CHAIN_CONTINUED_IN_SESSION_STATE
            reentry_reason = (
                "The completed quality-improvement step derived a compact bounded follow-on that started in the same governed invocation."
            )
            recommended_action = "monitor_in_session_follow_on"
        elif bool(completion_evaluation.get("completed", False)):
            if next_objective_id:
                if str(auto_continue_outputs.get("reason", "")).strip() == AUTO_CONTINUE_REASON_REVIEW_REQUIRED:
                    reentry_state = QUALITY_CHAIN_REVIEW_REQUIRED_STATE
                    reentry_reason = (
                        "The current quality-improvement step completed, but the next bounded quality objective still requires explicit operator review before continuation."
                    )
                    recommended_action = "review_then_relaunch"
                elif stop_reason in {STOP_REASON_MAX_CAP, STOP_REASON_SINGLE_CYCLE}:
                    reentry_state = QUALITY_CHAIN_DEFERRED_DUE_TO_CYCLE_BUDGET_STATE
                    reentry_reason = (
                        "The current quality-improvement step completed and a bounded follow-on was derived, but a fresh governed invocation is required because the hard cycle budget boundary was reached."
                    )
                    recommended_action = "relaunch_governed_execution"
                else:
                    reentry_state = QUALITY_CHAIN_STAGED_FOLLOW_ON_READY_STATE
                    reentry_reason = (
                        "The current quality-improvement step completed and a bounded follow-on is staged for the next governed invocation."
                    )
                    recommended_action = "relaunch_governed_execution"
            else:
                reentry_state = QUALITY_CHAIN_NO_FURTHER_WORK_STATE
                reentry_reason = (
                    "The completed quality-improvement step does not currently derive another bounded quality follow-on."
                )
                recommended_action = "stop_no_follow_on_required"
        elif skill_pack_completed and stop_reason in {STOP_REASON_MAX_CAP, STOP_REASON_SINGLE_CYCLE}:
            reentry_state = QUALITY_CHAIN_REENTRY_READY_STATE
            reentry_reason = (
                "The latest bounded skill-pack step completed successfully, but the approved quality objective still requires another governed invocation before completion can be re-evaluated."
            )
            recommended_action = "relaunch_governed_execution"
    payload = {
        "schema_name": SUCCESSOR_QUALITY_CHAIN_REENTRY_SCHEMA_NAME,
        "schema_version": SUCCESSOR_QUALITY_CHAIN_REENTRY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(review_outputs.get("review_summary", {}).get("directive_id", "")),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_objective_id": current_objective_id,
        "current_objective_class": current_objective_class,
        "current_objective_title": str(current_objective.get("title", "")),
        "current_objective_source_kind": current_source_kind,
        "current_objective_completed": bool(completion_evaluation.get("completed", False)),
        "stop_reason": str(stop_reason),
        "stop_detail": str(stop_detail),
        "reentry_state": reentry_state,
        "reentry_reason": reentry_reason,
        "recommended_action": recommended_action,
        "remaining_counted_cycle_budget": int(remaining_counted_cycle_budget or 0),
        "budget_staging_decision": str(
            budget_staging_decision or AUTO_CONTINUE_STAGING_NOT_APPLICABLE
        ),
        "budget_staging_rationale": str(budget_staging_rationale or "").strip(),
        "selected_skill_pack_id": selected_skill_pack_id,
        "selected_skill_pack_title": str(skill_pack_invocation.get("selected_skill_pack_title", "")),
        "skill_pack_result_state": str(skill_pack_result.get("result_state", "")),
        "quality_gap_id": str(quality_gap_summary.get("quality_gap_id", "")),
        "quality_gap_title": str(quality_gap_summary.get("quality_gap_title", "")),
        "quality_improvement_state": str(
            quality_improvement_summary.get("improvement_state", "")
        ),
        "next_quality_objective_id": next_objective_id,
        "next_quality_objective_class": next_objective_class,
        "next_quality_objective_title": str(next_objective_proposal.get("title", "")),
        "next_quality_objective_compact": bool(compact_follow_on),
        "next_quality_objective_operator_review_required": bool(
            next_objective_proposal.get("operator_review_required", False)
        ),
        "next_quality_objective_authorized": bool(
            effective_next_objective.get("continuation_authorized", False)
        )
        and str(effective_next_objective.get("objective_id", "")).strip() == next_objective_id,
        "auto_continue_reason": str(auto_continue_outputs.get("reason", "")),
        "auto_continue_transition_state": str(auto_continue_transition_state),
        "active_bounded_reference_target_id": str(
            quality_improvement_summary.get("active_bounded_reference_target_id", "")
        ),
        "protected_live_baseline_reference_id": str(
            quality_improvement_summary.get("protected_live_baseline_reference_id", "")
        ),
        "skill_pack_invocation_path": str(paths["skill_pack_invocation_path"]),
        "skill_pack_result_path": str(paths["skill_pack_result_path"]),
        "quality_gap_summary_path": str(paths["quality_gap_summary_path"]),
        "quality_improvement_summary_path": str(paths["quality_improvement_summary_path"]),
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
        "reference_target_consumption_path": str(paths["reference_target_consumption_path"]),
    }
    if str(runtime_event_log_path or "").strip():
        _write_json(
            paths["quality_chain_reentry_path"],
            payload,
            log_path=Path(str(runtime_event_log_path)),
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id or str(workspace_root.name),
            workspace_root=str(workspace_root),
            work_item_id=current_objective_id or "quality_chain_reentry",
            artifact_kind="successor_quality_chain_reentry_json",
        )
    else:
        paths["quality_chain_reentry_path"].parent.mkdir(parents=True, exist_ok=True)
        paths["quality_chain_reentry_path"].write_text(_dump(payload), encoding="utf-8")
    if str(runtime_event_log_path or "").strip():
        _event(
            Path(str(runtime_event_log_path)),
            event_type="successor_quality_chain_reentry_recorded",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id or str(workspace_root.name),
            workspace_root=str(workspace_root),
            current_objective_id=current_objective_id,
            reentry_state=reentry_state,
            recommended_action=recommended_action,
            next_quality_objective_id=next_objective_id,
            next_quality_objective_class=next_objective_class,
            compact_follow_on=bool(compact_follow_on),
            quality_chain_reentry_path=str(paths["quality_chain_reentry_path"]),
        )
    return payload


def _derive_next_step_from_continuation_pack(
    *,
    current_directive: dict[str, Any],
    continuation_pack: dict[str, Any],
    completion_evaluation: dict[str, Any],
    workspace_root: Path,
    reference_target_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    completed_by_id = {
        str(item.get("deliverable_id", "")): bool(item.get("completed", False))
        for item in list(completion_evaluation.get("deliverable_checks", []))
        if str(item.get("deliverable_id", "")).strip()
    }
    stages = [dict(item) for item in list(continuation_pack.get("stages", []))]
    selected_stage: dict[str, Any] = {}
    stage_reason = ""
    missing_deliverables = list(completion_evaluation.get("missing_required_deliverables", []))

    for stage in stages:
        requires_deliverables = [str(item).strip() for item in list(stage.get("requires_deliverables", [])) if str(item).strip()]
        missing_gate = [str(item).strip() for item in list(stage.get("missing_deliverables_gate", [])) if str(item).strip()]
        if not all(completed_by_id.get(item, False) for item in requires_deliverables):
            continue
        if not any(not completed_by_id.get(item, False) for item in missing_gate):
            continue
        selected_stage = {
            "stage_id": str(stage.get("stage_id", "")),
            "title": str(stage.get("title", "")),
            "cycle_kind": str(stage.get("cycle_kind", "")),
            "work_item_id": str(stage.get("work_item_id", "")),
            "rationale": str(stage.get("rationale", "")),
            "next_recommended_cycle": str(stage.get("next_recommended_cycle", "")),
            "requires_deliverables": requires_deliverables,
            "missing_deliverables_gate": missing_gate,
        }
        stage_reason = (
            f"selected {selected_stage['stage_id']} because "
            + ", ".join(missing_gate)
            + " remain incomplete under the bounded successor rubric"
        )
        break

    if not selected_stage and bool(completion_evaluation.get("completed", False)):
        stage_reason = "no further cycle is required because the bounded successor completion rubric is satisfied"
    elif not selected_stage:
        stage_reason = "no admissible continuation stage matched the current bounded deliverable state"

    return {
        "schema_name": NEXT_STEP_DERIVATION_SCHEMA_NAME,
        "schema_version": NEXT_STEP_DERIVATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "continuation_pack_id": str(continuation_pack.get("pack_id", "")),
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_root": str(workspace_root),
        "selected_stage": selected_stage,
        "reason": stage_reason,
        "admissible_work_remaining": bool(selected_stage),
        "next_recommended_cycle": str(selected_stage.get("next_recommended_cycle", "")),
        "missing_required_deliverables": missing_deliverables,
        "working_reference_target": dict(reference_target_context or {}),
        "reference_target_consumption_state": str(
            dict(reference_target_context or {}).get("consumption_state", "")
        ),
        "active_bounded_reference_target_id": str(
            dict(reference_target_context or {}).get(
                "active_bounded_reference_target_id",
                "",
            )
        ),
        "protected_live_baseline_reference_id": str(
            dict(reference_target_context or {}).get(
                "protected_live_baseline_reference_id",
                "",
            )
        ),
        "comparison_basis": str(
            dict(reference_target_context or {}).get("comparison_basis", "")
        ),
    }


def _derive_next_step_with_objective_context(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    completion_evaluation: dict[str, Any],
    base_next_step: dict[str, Any],
    reference_target_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reference_target_context = dict(
        reference_target_context
        or completion_evaluation.get("working_reference_target", {})
    )
    objective_context = dict(
        completion_evaluation.get(
            "current_objective",
            _current_objective_context(
                current_directive=current_directive,
                workspace_root=workspace_root,
            ),
        )
    )
    if str(objective_context.get("source_kind", "")).strip() != OBJECTIVE_SOURCE_APPROVED_RESEED:
        return {
            **dict(base_next_step),
            "current_objective": objective_context,
            "working_reference_target": dict(reference_target_context),
            "reference_target_consumption_state": str(
                reference_target_context.get("consumption_state", "")
            ),
            "active_bounded_reference_target_id": str(
                reference_target_context.get("active_bounded_reference_target_id", "")
            ),
            "protected_live_baseline_reference_id": str(
                reference_target_context.get("protected_live_baseline_reference_id", "")
            ),
            "comparison_basis": str(reference_target_context.get("comparison_basis", "")),
        }
    if bool(completion_evaluation.get("completed", False)):
        return {
            "schema_name": NEXT_STEP_DERIVATION_SCHEMA_NAME,
            "schema_version": NEXT_STEP_DERIVATION_SCHEMA_VERSION,
            "generated_at": _now(),
            "continuation_pack_id": "approved_reseed_objective",
            "directive_id": str(current_directive.get("directive_id", "")),
            "workspace_root": str(workspace_root),
            "selected_stage": {},
            "reason": str(completion_evaluation.get("reason", "")).strip()
            or "the approved bounded continuation objective is already complete",
            "admissible_work_remaining": False,
            "next_recommended_cycle": "operator_review_required",
            "missing_required_deliverables": list(
                completion_evaluation.get("missing_required_deliverables", [])
            ),
            "current_objective": objective_context,
            "working_reference_target": dict(reference_target_context),
            "reference_target_consumption_state": str(
                reference_target_context.get("consumption_state", "")
            ),
            "active_bounded_reference_target_id": str(
                reference_target_context.get("active_bounded_reference_target_id", "")
            ),
            "protected_live_baseline_reference_id": str(
                reference_target_context.get("protected_live_baseline_reference_id", "")
            ),
            "comparison_basis": str(reference_target_context.get("comparison_basis", "")),
        }
    selected_stage = _effective_objective_stage(str(objective_context.get("objective_id", "")))
    if not selected_stage:
        return {
            "schema_name": NEXT_STEP_DERIVATION_SCHEMA_NAME,
            "schema_version": NEXT_STEP_DERIVATION_SCHEMA_VERSION,
            "generated_at": _now(),
            "continuation_pack_id": "approved_reseed_objective",
            "directive_id": str(current_directive.get("directive_id", "")),
            "workspace_root": str(workspace_root),
            "selected_stage": {},
            "reason": (
                "the approved next objective is recorded, but this slice does not yet materialize a bounded "
                "execution stage for that objective"
            ),
            "admissible_work_remaining": False,
            "next_recommended_cycle": "operator_review_required",
            "missing_required_deliverables": list(
                completion_evaluation.get("missing_required_deliverables", [])
            ),
            "current_objective": objective_context,
            "working_reference_target": dict(reference_target_context),
            "reference_target_consumption_state": str(
                reference_target_context.get("consumption_state", "")
            ),
            "active_bounded_reference_target_id": str(
                reference_target_context.get("active_bounded_reference_target_id", "")
            ),
            "protected_live_baseline_reference_id": str(
                reference_target_context.get("protected_live_baseline_reference_id", "")
            ),
            "comparison_basis": str(reference_target_context.get("comparison_basis", "")),
        }
    return {
        "schema_name": NEXT_STEP_DERIVATION_SCHEMA_NAME,
        "schema_version": NEXT_STEP_DERIVATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "continuation_pack_id": "approved_reseed_objective",
        "directive_id": str(current_directive.get("directive_id", "")),
        "workspace_root": str(workspace_root),
        "selected_stage": selected_stage,
        "reason": (
            f"using the operator-approved bounded next objective {objective_context.get('objective_id', '')} "
            "as the current governed continuation target"
        ),
        "admissible_work_remaining": True,
        "next_recommended_cycle": str(selected_stage.get("next_recommended_cycle", "")),
        "missing_required_deliverables": list(
            completion_evaluation.get("missing_required_deliverables", [])
        ),
        "current_objective": objective_context,
        "working_reference_target": dict(reference_target_context),
        "reference_target_consumption_state": str(
            reference_target_context.get("consumption_state", "")
        ),
        "active_bounded_reference_target_id": str(
            reference_target_context.get("active_bounded_reference_target_id", "")
        ),
        "protected_live_baseline_reference_id": str(
            reference_target_context.get("protected_live_baseline_reference_id", "")
        ),
        "comparison_basis": str(reference_target_context.get("comparison_basis", "")),
    }


def _build_trusted_planning_context(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    cycle_index: int,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    work_item_id: str,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    baseline = _workspace_baseline(workspace_root)
    completion_pack, completion_source = _load_internal_knowledge_pack(
        session=session,
        source_id=INTERNAL_SUCCESSOR_COMPLETION_SOURCE_ID,
        expected_schema_name=SUCCESSOR_COMPLETION_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=SUCCESSOR_COMPLETION_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    continuation_pack, continuation_source = _load_internal_knowledge_pack(
        session=session,
        source_id=INTERNAL_WORKSPACE_CONTINUATION_SOURCE_ID,
        expected_schema_name=WORKSPACE_CONTINUATION_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=WORKSPACE_CONTINUATION_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    current_objective = _current_objective_context(
        current_directive=current_directive,
        workspace_root=workspace_root,
    )
    reference_target_consumption = _resolve_reference_target_consumption(
        current_directive=current_directive,
        workspace_root=workspace_root,
        current_objective=current_objective,
    )
    completion_evaluation = _evaluate_current_objective_completion(
        current_directive=current_directive,
        workspace_root=workspace_root,
        completion_pack=completion_pack,
        objective_context=current_objective,
        reference_target_context=reference_target_consumption,
    )
    base_next_step = _derive_next_step_from_continuation_pack(
        current_directive=current_directive,
        continuation_pack=continuation_pack,
        completion_evaluation=completion_evaluation,
        workspace_root=workspace_root,
        reference_target_context=reference_target_consumption,
    )
    next_step = _derive_next_step_with_objective_context(
        current_directive=current_directive,
        workspace_root=workspace_root,
        completion_evaluation=completion_evaluation,
        base_next_step=base_next_step,
        reference_target_context=reference_target_consumption,
    )
    missing_deliverables = {
        "schema_name": MISSING_DELIVERABLES_SCHEMA_NAME,
        "schema_version": MISSING_DELIVERABLES_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "missing_required_deliverables": list(completion_evaluation.get("missing_required_deliverables", [])),
        "missing_required_deliverable_count": len(list(completion_evaluation.get("missing_required_deliverables", []))),
        "next_recommended_cycle": str(next_step.get("next_recommended_cycle", "")),
        "reference_target": dict(reference_target_consumption),
    }
    planning_evidence = {
        "schema_name": TRUSTED_PLANNING_EVIDENCE_SCHEMA_NAME,
        "schema_version": TRUSTED_PLANNING_EVIDENCE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "cycle_index": int(cycle_index),
        "directive_trusted_sources": [str(item) for item in list(current_directive.get("trusted_sources", []))],
        "consulted_workspace_artifacts": {
            "bounded_work_summary_latest": str(paths["summary_path"]) if paths["summary_path"].exists() else "",
            "implementation_bundle_summary_latest": str(paths["implementation_summary_path"]) if paths["implementation_summary_path"].exists() else "",
            "workspace_artifact_index_latest": str(paths["workspace_artifact_index_path"]),
        },
        "knowledge_packs": [completion_source, continuation_source],
        "workspace_artifact_index": workspace_artifact_index,
        "baseline_state": {
            "has_planning_baseline": bool(baseline.get("has_planning_baseline", False)),
            "implementation_materialized": bool(baseline.get("implementation_materialized", False)),
            "continuation_gap_materialized": bool(baseline.get("continuation_gap_materialized", False)),
            "readiness_materialized": bool(baseline.get("readiness_materialized", False)),
            "promotion_bundle_materialized": bool(baseline.get("promotion_bundle_materialized", False)),
        },
        "current_objective": dict(current_objective),
        "reference_target": dict(reference_target_consumption),
    }

    latest_writes = [
        (paths["workspace_artifact_index_path"], workspace_artifact_index, "workspace_artifact_index_json"),
        (paths["trusted_planning_evidence_path"], planning_evidence, "trusted_planning_evidence_json"),
        (paths["missing_deliverables_path"], missing_deliverables, "missing_deliverables_json"),
        (paths["next_step_derivation_path"], next_step, "next_step_derivation_json"),
        (paths["completion_evaluation_path"], completion_evaluation, "completion_evaluation_json"),
        (
            paths["reference_target_consumption_path"],
            reference_target_consumption,
            "successor_reference_target_consumption_json",
        ),
    ]
    for artifact_path, artifact_payload, artifact_kind in latest_writes:
        _write_json(
            artifact_path,
            artifact_payload,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=work_item_id,
            artifact_kind=artifact_kind,
        )

    cycle_prefix = paths["cycles_root"] / f"cycle_{int(cycle_index):03d}"
    archive_rows = [
        (cycle_prefix.with_name(f"{cycle_prefix.name}_trusted_planning_evidence.json"), planning_evidence),
        (cycle_prefix.with_name(f"{cycle_prefix.name}_missing_deliverables.json"), missing_deliverables),
        (cycle_prefix.with_name(f"{cycle_prefix.name}_next_step_derivation.json"), next_step),
        (cycle_prefix.with_name(f"{cycle_prefix.name}_completion_evaluation.json"), completion_evaluation),
        (
            cycle_prefix.with_name(f"{cycle_prefix.name}_reference_target_consumption.json"),
            reference_target_consumption,
        ),
    ]
    for artifact_path, artifact_payload in archive_rows:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    _event(
        runtime_event_log_path,
        event_type="trusted_planning_evidence_consulted",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        consulted_sources=[
            str(item.get("source_id", ""))
            for item in list(planning_evidence.get("knowledge_packs", []))
            if bool(item.get("loaded", False))
        ],
        trusted_planning_evidence_path=str(paths["trusted_planning_evidence_path"]),
        active_bounded_reference_target_id=str(
            reference_target_consumption.get("active_bounded_reference_target_id", "")
        ),
        protected_live_baseline_reference_id=str(
            reference_target_consumption.get("protected_live_baseline_reference_id", "")
        ),
    )
    _event(
        runtime_event_log_path,
        event_type=(
            "reference_target_consumed"
            if str(reference_target_consumption.get("consumption_state", "")).strip()
            == REFERENCE_TARGET_CONSUMED_STATE
            else "reference_target_fallback"
        ),
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        consumption_state=str(reference_target_consumption.get("consumption_state", "")),
        active_bounded_reference_target_id=str(
            reference_target_consumption.get("active_bounded_reference_target_id", "")
        ),
        protected_live_baseline_reference_id=str(
            reference_target_consumption.get("protected_live_baseline_reference_id", "")
        ),
        fallback_reason=str(reference_target_consumption.get("fallback_reason", "")),
        comparison_basis=str(reference_target_consumption.get("comparison_basis", "")),
        reference_target_path=str(paths["reference_target_path"]),
        reference_target_consumption_path=str(paths["reference_target_consumption_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="missing_deliverables_identified",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        missing_required_deliverable_count=int(missing_deliverables.get("missing_required_deliverable_count", 0)),
        missing_deliverables_path=str(paths["missing_deliverables_path"]),
        active_bounded_reference_target_id=str(
            reference_target_consumption.get("active_bounded_reference_target_id", "")
        ),
    )
    _event(
        runtime_event_log_path,
        event_type="next_cycle_derived",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        stage_id=str(dict(next_step.get("selected_stage", {})).get("stage_id", "")),
        cycle_kind=str(dict(next_step.get("selected_stage", {})).get("cycle_kind", "")),
        next_recommended_cycle=str(next_step.get("next_recommended_cycle", "")),
        next_step_derivation_path=str(paths["next_step_derivation_path"]),
        active_bounded_reference_target_id=str(
            reference_target_consumption.get("active_bounded_reference_target_id", "")
        ),
    )
    _event(
        runtime_event_log_path,
        event_type="completion_evaluation_recorded",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        completed=bool(completion_evaluation.get("completed", False)),
        reason=str(completion_evaluation.get("reason", "")),
        completion_evaluation_path=str(paths["completion_evaluation_path"]),
        active_bounded_reference_target_id=str(
            reference_target_consumption.get("active_bounded_reference_target_id", "")
        ),
        reference_target_consumption_state=str(
            reference_target_consumption.get("consumption_state", "")
        ),
    )
    return {
        "planning_evidence": planning_evidence,
        "missing_deliverables": missing_deliverables,
        "next_step": next_step,
        "completion_evaluation": completion_evaluation,
        "reference_target_consumption": reference_target_consumption,
        "artifact_paths": {
            "trusted_planning_evidence_path": str(paths["trusted_planning_evidence_path"]),
            "missing_deliverables_path": str(paths["missing_deliverables_path"]),
            "next_step_derivation_path": str(paths["next_step_derivation_path"]),
            "completion_evaluation_path": str(paths["completion_evaluation_path"]),
            "workspace_artifact_index_path": str(paths["workspace_artifact_index_path"]),
            "reference_target_consumption_path": str(
                paths["reference_target_consumption_path"]
            ),
        },
    }


def _invocation_model_for_mode(controller_mode: str) -> str:
    return (
        MULTI_CYCLE_EXECUTION_MODEL
        if str(controller_mode).strip() == "multi_cycle"
        else CYCLE_EXECUTION_MODEL
    )


def _cycle_summary_archive_path(workspace_root: Path, cycle_index: int) -> Path:
    return _workspace_paths(workspace_root)["cycles_root"] / f"cycle_{int(cycle_index):03d}_summary.json"


def _directive_completion_evaluation(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    latest_cycle_summary: dict[str, Any],
) -> dict[str, Any]:
    completion_pack, completion_source = _load_internal_knowledge_pack(
        session=session,
        source_id=INTERNAL_SUCCESSOR_COMPLETION_SOURCE_ID,
        expected_schema_name=SUCCESSOR_COMPLETION_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=SUCCESSOR_COMPLETION_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    completion_evaluation = _evaluate_current_objective_completion(
        current_directive=current_directive,
        workspace_root=workspace_root,
        completion_pack=completion_pack,
    )
    return {
        **completion_evaluation,
        "directive_completion_possible": bool(completion_pack),
        "fallback_used": not bool(completion_source.get("loaded", False)),
        "latest_cycle_kind": str(latest_cycle_summary.get("cycle_kind", "")).strip(),
        "knowledge_pack_source": completion_source,
    }


def _augment_cycle_payloads(
    *,
    payload: dict[str, Any],
    workspace_root: Path,
    cycle_index: int,
    controller_mode: str,
    latest_cycle_summary: dict[str, Any],
    completion_evaluation: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    invocation_model = _invocation_model_for_mode(controller_mode)
    summary_artifact_path = str(
        dict(payload.get("work_cycle", {})).get("summary_artifact_path", "")
    ).strip() or str(_workspace_paths(workspace_root)["summary_path"])
    cycle_archive_path = _cycle_summary_archive_path(workspace_root, cycle_index)
    augmented_summary = {
        **dict(latest_cycle_summary),
        "cycle_index": int(cycle_index),
        "invocation_model": invocation_model,
        "controller_mode": str(controller_mode),
        "cycle_summary_archive_path": str(cycle_archive_path),
        "directive_completion_evaluation": completion_evaluation,
    }
    cycle_archive_path.parent.mkdir(parents=True, exist_ok=True)
    Path(summary_artifact_path).write_text(_dump(augmented_summary), encoding="utf-8")
    cycle_archive_path.write_text(_dump(augmented_summary), encoding="utf-8")

    work_cycle = {
        **dict(payload.get("work_cycle", {})),
        "cycle_index": int(cycle_index),
        "invocation_model": invocation_model,
        "controller_mode": str(controller_mode),
        "cycle_summary_archive_path": str(cycle_archive_path),
        "directive_completion_evaluation": completion_evaluation,
    }
    updated_payload = {
        **dict(payload),
        "work_cycle": work_cycle,
    }
    return updated_payload, augmented_summary, str(cycle_archive_path)


def _implementation_module_source(*, directive_id: str) -> str:
    return (
        dedent(
            f'''
            """Workspace-local helper for bounded successor review.

            Generated during a governed implementation-bearing cycle for
            `{directive_id}`.
            """

            from __future__ import annotations

            from dataclasses import asdict, dataclass
            from pathlib import Path
            from typing import Iterable


            KNOWN_WORKSPACE_CATEGORIES = ("plans", "docs", "src", "tests", "artifacts", "other")


            @dataclass(frozen=True)
            class WorkspaceArtifactRecord:
                relative_path: str
                category: str
                size_bytes: int


            def classify_workspace_artifact(relative_path: str) -> str:
                parts = [part for part in Path(relative_path).parts if part not in {{'.'}}]
                if not parts:
                    return "other"
                root = parts[0]
                if root in KNOWN_WORKSPACE_CATEGORIES[:-1]:
                    return root
                return "other"


            def iter_workspace_artifact_records(workspace_root: str | Path) -> list[WorkspaceArtifactRecord]:
                root = Path(workspace_root)
                if not root.exists():
                    return []
                records: list[WorkspaceArtifactRecord] = []
                for path in sorted(root.rglob("*")):
                    if not path.is_file():
                        continue
                    relative_path = path.relative_to(root).as_posix()
                    records.append(
                        WorkspaceArtifactRecord(
                            relative_path=relative_path,
                            category=classify_workspace_artifact(relative_path),
                            size_bytes=path.stat().st_size,
                        )
                    )
                return records


            def recommend_next_cycle(records: Iterable[WorkspaceArtifactRecord]) -> str:
                record_list = list(records)
                has_python_source = any(
                    record.category == "src" and record.relative_path.endswith(".py")
                    for record in record_list
                )
                has_python_tests = any(
                    record.category == "tests" and record.relative_path.endswith(".py")
                    for record in record_list
                )
                has_continuation_gap_analysis = any(
                    record.relative_path == "plans/successor_continuation_gap_analysis.md"
                    for record in record_list
                )
                has_successor_readiness_bundle = all(
                    any(record.relative_path == relative_path for record in record_list)
                    for relative_path in (
                        "src/successor_shell/successor_manifest.py",
                        "tests/test_successor_manifest.py",
                        "docs/successor_package_readiness_note.md",
                        "artifacts/successor_readiness_evaluation_latest.json",
                        "artifacts/successor_delivery_manifest_latest.json",
                    )
                )
                if has_successor_readiness_bundle:
                    return "operator_review_required"
                if has_continuation_gap_analysis:
                    return "materialize_successor_package_readiness_bundle"
                if has_python_source and has_python_tests:
                    return "plan_successor_package_gap_closure"
                if has_python_source:
                    return "add_workspace_local_tests"
                return "materialize_workspace_local_implementation"


            def build_workspace_artifact_index(workspace_root: str | Path) -> dict[str, object]:
                records = iter_workspace_artifact_records(workspace_root)
                category_counts: dict[str, int] = {{}}
                for record in records:
                    category_counts[record.category] = category_counts.get(record.category, 0) + 1
                return {{
                    "workspace_root": str(Path(workspace_root)),
                    "artifact_count": len(records),
                    "category_counts": category_counts,
                    "artifacts": [asdict(record) for record in records],
                    "next_recommended_cycle": recommend_next_cycle(records),
                }}


            def render_workspace_artifact_report(workspace_root: str | Path) -> str:
                index = build_workspace_artifact_index(workspace_root)
                lines = [
                    "Workspace Artifact Index",
                    "",
                    f"Workspace root: {{index['workspace_root']}}",
                    f"Artifact count: {{index['artifact_count']}}",
                    f"Next recommended cycle: {{index['next_recommended_cycle']}}",
                    "",
                    "Categories:",
                ]
                for category, count in sorted(dict(index["category_counts"]).items()):
                    lines.append(f"- {{category}}: {{count}}")
                return "\\n".join(lines)
            '''
        ).strip()
        + "\n"
    )


def _implementation_init_source(*, include_readiness_helpers: bool = False) -> str:
    readiness_import_block = ""
    readiness_exports = ""
    if include_readiness_helpers:
        readiness_import_block = (
            "from .successor_manifest import (\n"
            "    build_successor_delivery_manifest,\n"
            "    render_successor_readiness_report,\n"
            ")\n"
        )
        readiness_exports = (
            '    "build_successor_delivery_manifest",\n'
            '    "render_successor_readiness_report",\n'
        )
    return (
        dedent(
            f"""
            \"\"\"Workspace-local successor shell helpers.\"\"\"

            from .workspace_contract import (
                build_workspace_artifact_index,
                classify_workspace_artifact,
                recommend_next_cycle,
                render_workspace_artifact_report,
            )
            {readiness_import_block}

            __all__ = [
                "build_workspace_artifact_index",
                "classify_workspace_artifact",
                "recommend_next_cycle",
                "render_workspace_artifact_report",
{readiness_exports.rstrip()}
            ]
            """
        ).strip()
        + "\n"
    )


def _implementation_test_source() -> str:
    return (
        dedent(
            """
            from __future__ import annotations

            import importlib.util
            import sys
            import tempfile
            import unittest
            from pathlib import Path


            def _load_workspace_contract_module():
                module_path = Path(__file__).resolve().parents[1] / "src" / "successor_shell" / "workspace_contract.py"
                spec = importlib.util.spec_from_file_location("workspace_contract", module_path)
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"Unable to load workspace contract module from {module_path}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                return module


            class WorkspaceContractTests(unittest.TestCase):
                def test_build_workspace_artifact_index_groups_workspace_outputs(self) -> None:
                    module = _load_workspace_contract_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "plans").mkdir(parents=True, exist_ok=True)
                        (root / "src").mkdir(parents=True, exist_ok=True)
                        (root / "tests").mkdir(parents=True, exist_ok=True)
                        (root / "plans" / "bounded_work_cycle_plan.md").write_text("plan", encoding="utf-8")
                        (root / "src" / "module.py").write_text("print('ok')\\n", encoding="utf-8")
                        (root / "tests" / "test_module.py").write_text("assert True\\n", encoding="utf-8")

                        index = module.build_workspace_artifact_index(root)

                        self.assertEqual(index["category_counts"]["plans"], 1)
                        self.assertEqual(index["category_counts"]["src"], 1)
                        self.assertEqual(index["category_counts"]["tests"], 1)
                        self.assertEqual(
                            index["next_recommended_cycle"],
                            "plan_successor_package_gap_closure",
                        )

                def test_render_workspace_artifact_report_mentions_workspace_root(self) -> None:
                    module = _load_workspace_contract_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "artifacts").mkdir(parents=True, exist_ok=True)
                        (root / "artifacts" / "summary.json").write_text("{}", encoding="utf-8")

                        report = module.render_workspace_artifact_report(root)

                        self.assertIn("Workspace Artifact Index", report)
                        self.assertIn(str(root), report)


            if __name__ == "__main__":
                unittest.main()
            """
        ).strip()
        + "\n"
    )


def _implementation_note_text(
    *,
    directive_id: str,
    workspace_id: str,
    implementation_bundle_kind: str,
    deferred_items: list[dict[str, str]],
) -> str:
    return (
        "\n".join(
            [
                "# Successor Shell Iteration Notes",
                "",
                f"Directive ID: `{directive_id}`",
                f"Workspace: `{workspace_id}`",
                f"Implementation bundle: `{implementation_bundle_kind}`",
                "",
                "This cycle advances the workspace from planning-only artifacts into a small real implementation bundle.",
                "",
                "Implemented now:",
                "- a workspace-local Python package export under `src/successor_shell/`",
                "- a real artifact-index and review helper module under `src/successor_shell/workspace_contract.py`",
                "- an executable regression module under `tests/test_workspace_contract.py`",
                "- operator-readable JSON summaries for the implementation bundle and workspace artifact index",
                "",
                "Still deferred:",
                *[f"- {item['item']}: {item['reason']}" for item in deferred_items],
                "",
            ]
        )
        + "\n"
    )


def _continuation_gap_analysis_text(
    *,
    directive_id: str,
    workspace_id: str,
    missing_deliverables: list[dict[str, Any]],
    next_step: dict[str, Any],
) -> str:
    selected_stage = dict(next_step.get("selected_stage", {}))
    lines = [
        "# Successor Continuation Gap Analysis",
        "",
        f"Directive ID: `{directive_id}`",
        f"Workspace: `{workspace_id}`",
        "",
        "This planning cycle consulted internal trusted-source knowledge packs and current workspace artifacts",
        "to determine what bounded successor deliverables still remain inside the active workspace.",
        "",
        "Missing deliverables:",
    ]
    if missing_deliverables:
        lines.extend(
            [
                f"- `{str(item.get('deliverable_id', ''))}`: "
                + ", ".join(str(path) for path in list(item.get("missing_evidence_relative_paths", [])))
                for item in missing_deliverables
            ]
        )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "Selected next bounded step:",
            f"- stage: `{str(selected_stage.get('stage_id', '') or '<none>')}`",
            f"- cycle kind: `{str(selected_stage.get('cycle_kind', '') or '<none>')}`",
            f"- next recommended cycle: `{str(next_step.get('next_recommended_cycle', '') or '<none>')}`",
            f"- rationale: {str(next_step.get('reason', '') or '<none recorded>')}",
            "",
            "This remains bounded mutable-shell planning only. Protected-surface mutation remains excluded.",
            "",
        ]
    )
    return "\n".join(lines)


def _successor_manifest_source() -> str:
    return (
        dedent(
            """
            \"\"\"Workspace-local successor readiness helpers.\"\"\"

            from __future__ import annotations

            from pathlib import Path


            REQUIRED_SUCCESSOR_DELIVERABLES = (
                "plans/bounded_work_cycle_plan.md",
                "docs/mutable_shell_successor_design_note.md",
                "src/successor_shell/workspace_contract.py",
                "tests/test_workspace_contract.py",
                "plans/successor_continuation_gap_analysis.md",
                "docs/successor_package_readiness_note.md",
            )


            def build_successor_delivery_manifest(workspace_root: str | Path) -> dict[str, object]:
                root = Path(workspace_root)
                deliverables = []
                for relative_path in REQUIRED_SUCCESSOR_DELIVERABLES:
                    path = root / relative_path
                    deliverables.append(
                        {
                            "relative_path": relative_path,
                            "present": path.exists(),
                            "absolute_path": str(path),
                        }
                    )
                return {
                    "workspace_root": str(root),
                    "deliverables": deliverables,
                    "completion_ready": all(item["present"] for item in deliverables),
                }


            def render_successor_readiness_report(workspace_root: str | Path) -> str:
                manifest = build_successor_delivery_manifest(workspace_root)
                lines = [
                    "Successor Readiness Report",
                    "",
                    f"Workspace root: {manifest['workspace_root']}",
                    f"Completion ready: {manifest['completion_ready']}",
                    "",
                    "Deliverables:",
                ]
                for item in manifest["deliverables"]:
                    marker = "present" if item["present"] else "missing"
                    lines.append(f"- {marker}: {item['relative_path']}")
                return "\\n".join(lines)
            """
        ).strip()
        + "\n"
    )


def _successor_manifest_test_source() -> str:
    return (
        dedent(
            """
            from __future__ import annotations

            import importlib.util
            import sys
            import tempfile
            import unittest
            from pathlib import Path


            def _load_successor_manifest_module():
                module_path = Path(__file__).resolve().parents[1] / "src" / "successor_shell" / "successor_manifest.py"
                spec = importlib.util.spec_from_file_location("successor_manifest", module_path)
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"Unable to load successor manifest module from {module_path}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                return module


            class SuccessorManifestTests(unittest.TestCase):
                def test_build_successor_delivery_manifest_marks_missing_files(self) -> None:
                    module = _load_successor_manifest_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "plans").mkdir(parents=True, exist_ok=True)
                        (root / "plans" / "bounded_work_cycle_plan.md").write_text("plan", encoding="utf-8")

                        manifest = module.build_successor_delivery_manifest(root)

                        self.assertFalse(manifest["completion_ready"])
                        self.assertTrue(any(item["relative_path"] == "plans/bounded_work_cycle_plan.md" for item in manifest["deliverables"]))

                def test_render_successor_readiness_report_mentions_completion_ready(self) -> None:
                    module = _load_successor_manifest_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        report = module.render_successor_readiness_report(root)
                        self.assertIn("Successor Readiness Report", report)
                        self.assertIn("Completion ready:", report)


            if __name__ == "__main__":
                unittest.main()
            """
        ).strip()
        + "\n"
    )


def _readiness_note_text(
    *,
    directive_id: str,
    workspace_id: str,
    deferred_items: list[dict[str, str]],
) -> str:
    return (
        "\n".join(
            [
                "# Successor Package Readiness Note",
                "",
                f"Directive ID: `{directive_id}`",
                f"Workspace: `{workspace_id}`",
                "",
                "This implementation-bearing cycle materializes a bounded successor readiness bundle",
                "inside the active workspace only.",
                "",
                "Implemented now:",
                "- `src/successor_shell/successor_manifest.py`",
                "- `tests/test_successor_manifest.py`",
                "- `docs/successor_package_readiness_note.md`",
                "- `artifacts/successor_readiness_evaluation_latest.json`",
                "- `artifacts/successor_delivery_manifest_latest.json`",
                "",
                "Still deferred:",
                *[f"- {item['item']}: {item['reason']}" for item in deferred_items],
                "",
            ]
        )
        + "\n"
    )


def _implementation_module_source_with_quality_review(
    *,
    directive_id: str,
    reference_target_id: str,
) -> str:
    return (
        dedent(
            f'''
            """Workspace-local helper for bounded successor review.

            Quality-review revision generated during a governed implementation-bearing
            cycle for `{directive_id}` against reference target `{reference_target_id or "current_bounded_baseline_expectations_v1"}`.
            """

            from __future__ import annotations

            from dataclasses import asdict, dataclass
            from pathlib import Path
            from typing import Iterable


            KNOWN_WORKSPACE_CATEGORIES = ("plans", "docs", "src", "tests", "artifacts", "other")
            PRIORITY_WORKSPACE_ARTIFACTS = (
                "plans/bounded_work_cycle_plan.md",
                "docs/mutable_shell_successor_design_note.md",
                "src/successor_shell/workspace_contract.py",
                "tests/test_workspace_contract.py",
                "artifacts/workspace_artifact_index_latest.json",
            )
            REFERENCE_TARGET_ID = "{reference_target_id or "current_bounded_baseline_expectations_v1"}"


            @dataclass(frozen=True)
            class WorkspaceArtifactRecord:
                relative_path: str
                category: str
                size_bytes: int


            def classify_workspace_artifact(relative_path: str) -> str:
                parts = [part for part in Path(relative_path).parts if part not in {{'.'}}]
                if not parts:
                    return "other"
                root = parts[0]
                if root in KNOWN_WORKSPACE_CATEGORIES[:-1]:
                    return root
                return "other"


            def iter_workspace_artifact_records(workspace_root: str | Path) -> list[WorkspaceArtifactRecord]:
                root = Path(workspace_root)
                if not root.exists():
                    return []
                records: list[WorkspaceArtifactRecord] = []
                for path in sorted(root.rglob("*")):
                    if not path.is_file():
                        continue
                    relative_path = path.relative_to(root).as_posix()
                    records.append(
                        WorkspaceArtifactRecord(
                            relative_path=relative_path,
                            category=classify_workspace_artifact(relative_path),
                            size_bytes=path.stat().st_size,
                        )
                    )
                return records


            def recommend_next_cycle(records: Iterable[WorkspaceArtifactRecord]) -> str:
                record_list = list(records)
                has_python_source = any(
                    record.category == "src" and record.relative_path.endswith(".py")
                    for record in record_list
                )
                has_python_tests = any(
                    record.category == "tests" and record.relative_path.endswith(".py")
                    for record in record_list
                )
                has_continuation_gap_analysis = any(
                    record.relative_path == "plans/successor_continuation_gap_analysis.md"
                    for record in record_list
                )
                has_successor_readiness_bundle = all(
                    any(record.relative_path == relative_path for record in record_list)
                    for relative_path in (
                        "src/successor_shell/successor_manifest.py",
                        "tests/test_successor_manifest.py",
                        "docs/successor_package_readiness_note.md",
                        "artifacts/successor_readiness_evaluation_latest.json",
                        "artifacts/successor_delivery_manifest_latest.json",
                    )
                )
                if has_successor_readiness_bundle:
                    return "operator_review_required"
                if has_continuation_gap_analysis:
                    return "materialize_successor_package_readiness_bundle"
                if has_python_source and has_python_tests:
                    return "plan_successor_package_gap_closure"
                if has_python_source:
                    return "add_workspace_local_tests"
                return "materialize_workspace_local_implementation"


            def priority_workspace_artifacts(workspace_root: str | Path) -> dict[str, object]:
                root = Path(workspace_root)
                present = [relative_path for relative_path in PRIORITY_WORKSPACE_ARTIFACTS if (root / relative_path).exists()]
                missing = [relative_path for relative_path in PRIORITY_WORKSPACE_ARTIFACTS if relative_path not in present]
                return {{
                    "reference_target_id": REFERENCE_TARGET_ID,
                    "priority_artifacts_present": present,
                    "missing_priority_artifacts": missing,
                    "priority_artifact_count": len(present),
                }}


            def build_workspace_artifact_index(workspace_root: str | Path) -> dict[str, object]:
                records = iter_workspace_artifact_records(workspace_root)
                category_counts: dict[str, int] = {{}}
                for record in records:
                    category_counts[record.category] = category_counts.get(record.category, 0) + 1
                priority = priority_workspace_artifacts(workspace_root)
                return {{
                    "workspace_root": str(Path(workspace_root)),
                    "artifact_count": len(records),
                    "category_counts": category_counts,
                    "artifacts": [asdict(record) for record in records],
                    "priority_artifacts": priority,
                    "next_recommended_cycle": recommend_next_cycle(records),
                }}


            def render_workspace_artifact_report(workspace_root: str | Path) -> str:
                index = build_workspace_artifact_index(workspace_root)
                priority = dict(index.get("priority_artifacts", {{}}))
                lines = [
                    "Workspace Artifact Index",
                    "",
                    f"Workspace root: {{index['workspace_root']}}",
                    f"Artifact count: {{index['artifact_count']}}",
                    f"Reference target: {{priority.get('reference_target_id', '')}}",
                    f"Priority artifacts present: {{priority.get('priority_artifact_count', 0)}}",
                    f"Next recommended cycle: {{index['next_recommended_cycle']}}",
                    "",
                    "Categories:",
                ]
                for category, count in sorted(dict(index["category_counts"]).items()):
                    lines.append(f"- {{category}}: {{count}}")
                if priority.get("missing_priority_artifacts"):
                    lines.extend(["", "Missing priority artifacts:"])
                    for relative_path in priority["missing_priority_artifacts"]:
                        lines.append(f"- {{relative_path}}")
                return "\\n".join(lines)
            '''
        ).strip()
        + "\n"
    )


def _implementation_test_source_with_quality_review() -> str:
    return (
        dedent(
            """
            from __future__ import annotations

            import importlib.util
            import sys
            import tempfile
            import unittest
            from pathlib import Path


            def _load_workspace_contract_module():
                module_path = Path(__file__).resolve().parents[1] / "src" / "successor_shell" / "workspace_contract.py"
                spec = importlib.util.spec_from_file_location("workspace_contract", module_path)
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"Unable to load workspace contract module from {module_path}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                return module


            class WorkspaceContractTests(unittest.TestCase):
                def test_build_workspace_artifact_index_groups_workspace_outputs(self) -> None:
                    module = _load_workspace_contract_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "plans").mkdir(parents=True, exist_ok=True)
                        (root / "src").mkdir(parents=True, exist_ok=True)
                        (root / "tests").mkdir(parents=True, exist_ok=True)
                        (root / "plans" / "bounded_work_cycle_plan.md").write_text("plan", encoding="utf-8")
                        (root / "src" / "module.py").write_text("print('ok')\\n", encoding="utf-8")
                        (root / "tests" / "test_module.py").write_text("assert True\\n", encoding="utf-8")

                        index = module.build_workspace_artifact_index(root)

                        self.assertEqual(index["category_counts"]["plans"], 1)
                        self.assertEqual(index["category_counts"]["src"], 1)
                        self.assertEqual(index["category_counts"]["tests"], 1)
                        self.assertEqual(index["next_recommended_cycle"], "plan_successor_package_gap_closure")

                def test_priority_workspace_artifacts_reports_missing_items(self) -> None:
                    module = _load_workspace_contract_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "plans").mkdir(parents=True, exist_ok=True)
                        (root / "plans" / "bounded_work_cycle_plan.md").write_text("plan", encoding="utf-8")

                        summary = module.priority_workspace_artifacts(root)

                        self.assertGreater(len(summary["missing_priority_artifacts"]), 0)
                        self.assertIn("reference_target_id", summary)

                def test_render_workspace_artifact_report_mentions_reference_target(self) -> None:
                    module = _load_workspace_contract_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "artifacts").mkdir(parents=True, exist_ok=True)
                        (root / "artifacts" / "summary.json").write_text("{}", encoding="utf-8")

                        report = module.render_workspace_artifact_report(root)

                        self.assertIn("Workspace Artifact Index", report)
                        self.assertIn("Reference target:", report)


            if __name__ == "__main__":
                unittest.main()
            """
        ).strip()
        + "\n"
    )


def _successor_manifest_source_with_quality_pack(*, reference_target_id: str) -> str:
    return (
        dedent(
            f"""
            \"\"\"Workspace-local successor readiness helpers.\"\"\"

            from __future__ import annotations

            from pathlib import Path


            REFERENCE_TARGET_ID = "{reference_target_id or "current_bounded_baseline_expectations_v1"}"
            REQUIRED_SUCCESSOR_GROUPS = {{
                "planning": (
                    "plans/bounded_work_cycle_plan.md",
                    "docs/mutable_shell_successor_design_note.md",
                    "plans/successor_continuation_gap_analysis.md",
                ),
                "implementation": (
                    "src/successor_shell/workspace_contract.py",
                    "tests/test_workspace_contract.py",
                ),
                "readiness": (
                    "src/successor_shell/successor_manifest.py",
                    "tests/test_successor_manifest.py",
                    "docs/successor_package_readiness_note.md",
                ),
            }}


            def build_successor_delivery_manifest(workspace_root: str | Path) -> dict[str, object]:
                root = Path(workspace_root)
                deliverables = []
                group_summaries = []
                missing_relative_paths: list[str] = []
                for group_id, relative_paths in REQUIRED_SUCCESSOR_GROUPS.items():
                    group_rows = []
                    for relative_path in relative_paths:
                        path = root / relative_path
                        present = path.exists()
                        group_rows.append(
                            {{
                                "relative_path": relative_path,
                                "present": present,
                                "absolute_path": str(path),
                            }}
                        )
                        if not present:
                            missing_relative_paths.append(relative_path)
                    group_summaries.append(
                        {{
                            "group_id": group_id,
                            "required_relative_paths": list(relative_paths),
                            "completed": all(item["present"] for item in group_rows),
                        }}
                    )
                    deliverables.extend(group_rows)
                completion_ready = not missing_relative_paths
                return {{
                    "workspace_root": str(root),
                    "reference_target_id": REFERENCE_TARGET_ID,
                    "deliverables": deliverables,
                    "group_summaries": group_summaries,
                    "missing_relative_paths": missing_relative_paths,
                    "completion_ready": completion_ready,
                }}


            def build_successor_readiness_summary(workspace_root: str | Path) -> dict[str, object]:
                manifest = build_successor_delivery_manifest(workspace_root)
                return {{
                    "workspace_root": manifest["workspace_root"],
                    "reference_target_id": manifest["reference_target_id"],
                    "completion_ready": manifest["completion_ready"],
                    "missing_relative_paths": list(manifest["missing_relative_paths"]),
                    "completed_group_count": sum(1 for item in manifest["group_summaries"] if item["completed"]),
                    "required_group_count": len(manifest["group_summaries"]),
                }}


            def render_successor_readiness_report(workspace_root: str | Path) -> str:
                manifest = build_successor_delivery_manifest(workspace_root)
                summary = build_successor_readiness_summary(workspace_root)
                lines = [
                    "Successor Readiness Report",
                    "",
                    f"Workspace root: {{manifest['workspace_root']}}",
                    f"Reference target: {{manifest['reference_target_id']}}",
                    f"Completion ready: {{manifest['completion_ready']}}",
                    f"Completed groups: {{summary['completed_group_count']}} / {{summary['required_group_count']}}",
                    "",
                    "Deliverables:",
                ]
                for item in manifest["deliverables"]:
                    marker = "present" if item["present"] else "missing"
                    lines.append(f"- {{marker}}: {{item['relative_path']}}")
                return "\\n".join(lines)
            """
        ).strip()
        + "\n"
    )


def _successor_manifest_test_source_with_quality_pack() -> str:
    return (
        dedent(
            """
            from __future__ import annotations

            import importlib.util
            import sys
            import tempfile
            import unittest
            from pathlib import Path


            def _load_successor_manifest_module():
                module_path = Path(__file__).resolve().parents[1] / "src" / "successor_shell" / "successor_manifest.py"
                spec = importlib.util.spec_from_file_location("successor_manifest", module_path)
                if spec is None or spec.loader is None:
                    raise RuntimeError(f"Unable to load successor manifest module from {module_path}")
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                return module


            class SuccessorManifestTests(unittest.TestCase):
                def test_build_successor_delivery_manifest_marks_missing_files(self) -> None:
                    module = _load_successor_manifest_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        (root / "plans").mkdir(parents=True, exist_ok=True)
                        (root / "plans" / "bounded_work_cycle_plan.md").write_text("plan", encoding="utf-8")

                        manifest = module.build_successor_delivery_manifest(root)

                        self.assertFalse(manifest["completion_ready"])
                        self.assertTrue(any(item["relative_path"] == "plans/bounded_work_cycle_plan.md" for item in manifest["deliverables"]))
                        self.assertGreater(len(manifest["missing_relative_paths"]), 0)

                def test_build_successor_readiness_summary_counts_completed_groups(self) -> None:
                    module = _load_successor_manifest_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        summary = module.build_successor_readiness_summary(root)
                        self.assertIn("completed_group_count", summary)
                        self.assertIn("required_group_count", summary)

                def test_render_successor_readiness_report_mentions_reference_target(self) -> None:
                    module = _load_successor_manifest_module()
                    with tempfile.TemporaryDirectory() as tmp:
                        root = Path(tmp)
                        report = module.render_successor_readiness_report(root)
                        self.assertIn("Successor Readiness Report", report)
                        self.assertIn("Reference target:", report)


            if __name__ == "__main__":
                unittest.main()
            """
        ).strip()
        + "\n"
    )


def _workspace_review_iteration_note_text(
    *,
    directive_id: str,
    workspace_id: str,
    reference_target_id: str,
) -> str:
    return (
        "\n".join(
            [
                "# Successor Shell Iteration Notes",
                "",
                f"Directive ID: `{directive_id}`",
                f"Workspace: `{workspace_id}`",
                f"Reference target: `{reference_target_id or 'current_bounded_baseline_expectations_v1'}`",
                "",
                "This bounded skill-pack revision strengthened the workspace-local review helpers",
                "relative to the current bounded reference target without mutating protected surfaces.",
                "",
                "Improved now:",
                "- richer priority-artifact reporting in `src/successor_shell/workspace_contract.py`",
                "- deeper regression coverage in `tests/test_workspace_contract.py`",
                "- explicit quality-gap and improvement artifacts under `artifacts/`",
                "",
            ]
        )
        + "\n"
    )


def _manifest_quality_readiness_note_text(
    *,
    directive_id: str,
    workspace_id: str,
    reference_target_id: str,
    deferred_items: list[dict[str, str]],
) -> str:
    return (
        "\n".join(
            [
                "# Successor Package Readiness Note",
                "",
                f"Directive ID: `{directive_id}`",
                f"Workspace: `{workspace_id}`",
                f"Reference target: `{reference_target_id or 'current_bounded_baseline_expectations_v1'}`",
                "",
                "This bounded skill-pack revision improved successor manifest coherence and readiness reporting",
                "inside the active workspace only.",
                "",
                "Improved now:",
                "- grouped deliverable coverage in `src/successor_shell/successor_manifest.py`",
                "- stronger readiness regression coverage in `tests/test_successor_manifest.py`",
                "- richer readiness summary and delivery manifest outputs",
                "",
                "Still deferred:",
                *[f"- {item['item']}: {item['reason']}" for item in deferred_items],
                "",
            ]
        )
        + "\n"
    )


def _docs_readiness_review_text(
    *,
    directive_id: str,
    workspace_id: str,
    reference_target_id: str,
) -> str:
    return (
        "\n".join(
            [
                "# Successor Docs And Readiness Review",
                "",
                f"Directive ID: `{directive_id}`",
                f"Workspace: `{workspace_id}`",
                f"Reference target: `{reference_target_id or 'current_bounded_baseline_expectations_v1'}`",
                "",
                "This bounded skill-pack revision tightened operator-readable readiness documentation",
                "relative to the current bounded reference target without expanding permissions.",
                "",
                "Improved now:",
                "- clearer readiness checkpoints in `docs/successor_package_readiness_note.md`",
                "- explicit operator review notes in `docs/successor_docs_readiness_review.md`",
                "- bounded focus on workspace-local artifacts only",
                "",
            ]
        )
        + "\n"
    )


def _handoff_completeness_note_text(
    *,
    directive_id: str,
    workspace_id: str,
    reference_target_id: str,
) -> str:
    return (
        "\n".join(
            [
                "# Successor Handoff Completeness Note",
                "",
                f"Directive ID: `{directive_id}`",
                f"Workspace: `{workspace_id}`",
                f"Reference target: `{reference_target_id or 'current_bounded_baseline_expectations_v1'}`",
                "",
                "This bounded skill-pack revision strengthened candidate handoff completeness inside",
                "the active workspace only.",
                "",
                "Improved now:",
                "- explicit handoff completeness note for the admitted candidate lifecycle",
                "- clearer linkage from promotion bundle artifacts to admitted-candidate handoff state",
                "- operator-readable bounded handoff summary without mutating the protected baseline",
                "",
            ]
        )
        + "\n"
    )


def _successor_quality_dimension_definitions() -> list[dict[str, Any]]:
    return [
        {
            "dimension_id": "manifest_handoff_coherence",
            "title": "Manifest / handoff coherence",
            "priority_rank": 10,
            "priority_level": "high",
            "objective_class": "improve_successor_package_readiness",
            "skill_pack_id": INTERNAL_SUCCESSOR_MANIFEST_QUALITY_SKILL_PACK_ID,
            "required_relative_paths": [
                "src/successor_shell/successor_manifest.py",
                "tests/test_successor_manifest.py",
                "docs/successor_package_readiness_note.md",
                "artifacts/successor_delivery_manifest_latest.json",
                "artifacts/successor_readiness_evaluation_latest.json",
            ],
            "resolution_marker_relative_paths": [
                "artifacts/successor_quality_improvement_summary_latest.json",
            ],
            "requires_recorded_pack_resolution": True,
            "dimension_rationale": "Track whether the successor manifest, readiness note, and delivery outputs are coherent enough for bounded handoff review.",
        },
        {
            "dimension_id": "test_delta_quality",
            "title": "Test coverage / test-delta quality",
            "priority_rank": 20,
            "priority_level": "high",
            "objective_class": "strengthen_successor_test_coverage",
            "skill_pack_id": INTERNAL_SUCCESSOR_TEST_STRENGTHENING_SKILL_PACK_ID,
            "required_relative_paths": [
                "tests/test_workspace_contract.py",
                "tests/test_successor_manifest.py",
            ],
            "resolution_marker_relative_paths": [
                "tests/test_workspace_contract.py",
            ],
            "requires_recorded_pack_resolution": True,
            "dimension_rationale": "Track whether bounded regression coverage is materially stronger than the admitted-candidate reference target.",
        },
        {
            "dimension_id": "docs_readiness_coherence",
            "title": "Docs / readiness coherence",
            "priority_rank": 30,
            "priority_level": "medium",
            "objective_class": "refine_successor_docs_readiness",
            "skill_pack_id": INTERNAL_SUCCESSOR_DOCS_READINESS_SKILL_PACK_ID,
            "required_relative_paths": [
                "docs/successor_package_readiness_note.md",
                "docs/successor_docs_readiness_review.md",
            ],
            "resolution_marker_relative_paths": [
                "docs/successor_docs_readiness_review.md",
            ],
            "requires_recorded_pack_resolution": False,
            "dimension_rationale": "Track whether workspace-local readiness documentation is explicit, auditable, and aligned with the current bounded reference target.",
        },
        {
            "dimension_id": "artifact_index_consistency",
            "title": "Artifact / index consistency",
            "priority_rank": 40,
            "priority_level": "medium",
            "objective_class": "refine_successor_artifact_index_consistency",
            "skill_pack_id": INTERNAL_SUCCESSOR_ARTIFACT_INDEX_CONSISTENCY_SKILL_PACK_ID,
            "required_relative_paths": [
                "artifacts/workspace_artifact_index_latest.json",
                "artifacts/successor_artifact_index_consistency_latest.json",
            ],
            "resolution_marker_relative_paths": [
                "artifacts/successor_artifact_index_consistency_latest.json",
            ],
            "requires_recorded_pack_resolution": False,
            "dimension_rationale": "Track whether the workspace artifact index and supporting audit metadata remain coherent as successor work evolves.",
        },
        {
            "dimension_id": "package_handoff_completeness",
            "title": "Package-handoff completeness",
            "priority_rank": 50,
            "priority_level": "medium",
            "objective_class": "improve_successor_handoff_completeness",
            "skill_pack_id": INTERNAL_SUCCESSOR_HANDOFF_COMPLETENESS_SKILL_PACK_ID,
            "required_relative_paths": [
                "docs/successor_promotion_bundle_note.md",
                "docs/successor_handoff_completeness_note.md",
                "artifacts/successor_candidate_promotion_bundle_latest.json",
                "artifacts/successor_admitted_candidate_handoff_latest.json",
            ],
            "resolution_marker_relative_paths": [
                "docs/successor_handoff_completeness_note.md",
            ],
            "requires_recorded_pack_resolution": False,
            "dimension_rationale": "Track whether the bounded successor handoff bundle is complete enough to carry forward as a stronger candidate package.",
        },
        {
            "dimension_id": "workspace_review_completeness",
            "title": "Workspace review completeness",
            "priority_rank": 60,
            "priority_level": "low",
            "objective_class": "review_and_expand_workspace_local_implementation",
            "skill_pack_id": INTERNAL_SUCCESSOR_WORKSPACE_REVIEW_SKILL_PACK_ID,
            "required_relative_paths": [
                "src/successor_shell/workspace_contract.py",
                "tests/test_workspace_contract.py",
                "docs/successor_shell_iteration_notes.md",
                "artifacts/successor_review_summary_latest.json",
            ],
            "resolution_marker_relative_paths": [
                "docs/successor_shell_iteration_notes.md",
            ],
            "requires_recorded_pack_resolution": False,
            "dimension_rationale": "Track whether workspace-local implementation and review helpers remain complete and operator-auditable.",
        },
        {
            "dimension_id": "bounded_code_structure_clarity",
            "title": "Bounded code-structure clarity",
            "priority_rank": 70,
            "priority_level": "low",
            "objective_class": "",
            "skill_pack_id": "",
            "required_relative_paths": [
                "src/successor_shell/__init__.py",
                "src/successor_shell/workspace_contract.py",
                "src/successor_shell/successor_manifest.py",
            ],
            "resolution_marker_relative_paths": [
                "src/successor_shell/__init__.py",
            ],
            "requires_recorded_pack_resolution": False,
            "dimension_rationale": "Track whether the bounded successor modules remain legible and well-organized inside the active workspace.",
        },
    ]


def _objective_title_for_quality_dimension(definition: dict[str, Any]) -> str:
    objective_class = str(definition.get("objective_class", "")).strip()
    return _humanize_objective_id(objective_class) if objective_class else ""


def _quality_dimension_definition_for_skill_pack(skill_pack_id: str) -> dict[str, Any]:
    pack_id = str(skill_pack_id or "").strip()
    if not pack_id:
        return {}
    for definition in _successor_quality_dimension_definitions():
        if str(definition.get("skill_pack_id", "")).strip() == pack_id:
            return dict(definition)
    return {}


def _quality_dimension_definition_for_id(dimension_id: str) -> dict[str, Any]:
    token = str(dimension_id or "").strip()
    if not token:
        return {}
    for definition in _successor_quality_dimension_definitions():
        if str(definition.get("dimension_id", "")).strip() == token:
            return dict(definition)
    return {}


def _evaluate_successor_quality_roadmap_state(
    *,
    workspace_root: Path,
    current_objective: dict[str, Any],
    reference_target_context: dict[str, Any],
    latest_skill_pack_invocation: dict[str, Any],
    latest_skill_pack_result: dict[str, Any],
    latest_quality_gap_summary: dict[str, Any],
    latest_quality_improvement_summary: dict[str, Any],
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    prior_roadmap = load_json(paths["quality_roadmap_path"])
    prior_dimensions = {
        str(item.get("dimension_id", "")).strip(): dict(item)
        for item in list(
            prior_roadmap.get("tracked_dimensions", prior_roadmap.get("dimensions", []))
        )
        if str(item.get("dimension_id", "")).strip()
    }
    latest_skill_pack_id = str(
        latest_skill_pack_result.get("selected_skill_pack_id", "")
    ).strip() or str(latest_skill_pack_invocation.get("selected_skill_pack_id", "")).strip()
    latest_skill_pack_title = str(
        latest_skill_pack_result.get("selected_skill_pack_title", "")
    ).strip() or str(latest_skill_pack_invocation.get("selected_skill_pack_title", "")).strip()
    latest_result_complete = str(
        latest_skill_pack_result.get("result_state", "")
    ).strip() == "complete"
    latest_improvement_complete = str(
        latest_quality_improvement_summary.get("improvement_state", "")
    ).strip() == "complete"
    latest_pack_complete = latest_result_complete and latest_improvement_complete
    latest_improved_relative = bool(
        latest_quality_improvement_summary.get("improved_relative_to_reference_target", False)
    )
    latest_quality_gap_id = str(
        latest_quality_gap_summary.get("quality_gap_id", "")
    ).strip()
    current_objective_class = str(current_objective.get("objective_class", "")).strip()

    dimension_rows: list[dict[str, Any]] = []
    for definition in _successor_quality_dimension_definitions():
        dimension_id = str(definition.get("dimension_id", "")).strip()
        prior_row = dict(prior_dimensions.get(dimension_id, {}))
        required_relative_paths = [
            str(item).strip()
            for item in list(definition.get("required_relative_paths", []))
            if str(item).strip()
        ]
        evidence_rows = [
            _relative_path_status(workspace_root, relative_path)
            for relative_path in required_relative_paths
        ]
        missing_relative_paths = [
            str(item.get("relative_path", ""))
            for item in evidence_rows
            if not bool(item.get("present", False))
        ]
        marker_relative_paths = [
            str(item).strip()
            for item in list(definition.get("resolution_marker_relative_paths", []))
            if str(item).strip()
        ]
        marker_rows = [
            _relative_path_status(workspace_root, relative_path)
            for relative_path in marker_relative_paths
        ]
        marker_present = bool(marker_rows) and all(
            bool(item.get("present", False)) for item in marker_rows
        )
        skill_pack_id = str(definition.get("skill_pack_id", "")).strip()
        current_pack_completed = bool(
            latest_pack_complete and skill_pack_id and latest_skill_pack_id == skill_pack_id
        )
        prior_resolved = (
            str(prior_row.get("state", "")).strip() == QUALITY_DIMENSION_RESOLVED_STATE
        )
        prior_resolution_still_supported = bool(
            prior_resolved and not missing_relative_paths
        )
        resolved_by_marker = marker_present and not bool(
            definition.get("requires_recorded_pack_resolution", False)
        )
        if (
            current_pack_completed
            or prior_resolution_still_supported
            or resolved_by_marker
        ):
            state = QUALITY_DIMENSION_RESOLVED_STATE
        elif any(bool(item.get("present", False)) for item in evidence_rows + marker_rows):
            state = QUALITY_DIMENSION_PARTIAL_STATE
        else:
            state = QUALITY_DIMENSION_WEAK_STATE

        improved_relative = bool(
            prior_row.get("improved_relative_to_reference_target", False)
        )
        last_completed_skill_pack_id = str(
            prior_row.get("last_completed_skill_pack_id", "")
        ).strip()
        last_completed_skill_pack_title = str(
            prior_row.get("last_completed_skill_pack_title", "")
        ).strip()
        last_improvement_state = str(
            prior_row.get("last_improvement_state", "")
        ).strip()
        last_quality_gap_id = str(prior_row.get("last_quality_gap_id", "")).strip()

        if current_pack_completed:
            improved_relative = latest_improved_relative
            last_completed_skill_pack_id = latest_skill_pack_id
            last_completed_skill_pack_title = latest_skill_pack_title
            last_improvement_state = str(
                latest_quality_improvement_summary.get("improvement_state", "")
            ).strip()
            last_quality_gap_id = latest_quality_gap_id
        elif resolved_by_marker and not last_completed_skill_pack_id:
            last_completed_skill_pack_id = skill_pack_id
            last_completed_skill_pack_title = _objective_title_for_quality_dimension(definition)
            last_improvement_state = "complete"
            improved_relative = improved_relative or bool(
                reference_target_context.get("active_bounded_reference_target_id", "")
            )

        rationale = ""
        if current_pack_completed:
            rationale = (
                "A bounded skill-pack improvement for this dimension completed successfully relative to the active bounded reference target."
            )
        elif prior_resolution_still_supported:
            rationale = str(prior_row.get("dimension_rationale", "")).strip() or (
                "This dimension was already resolved by an earlier bounded quality-improvement step."
            )
        elif resolved_by_marker:
            rationale = (
                "The workspace already contains the explicit marker artifacts required to treat this dimension as resolved."
            )
        elif state == QUALITY_DIMENSION_PARTIAL_STATE:
            rationale = (
                "Some bounded artifacts for this dimension are present, but a full quality-improvement closeout is not yet recorded."
            )
        else:
            rationale = (
                "This quality dimension remains weak relative to the active bounded reference target and still needs a bounded follow-on."
            )

        dimension_rows.append(
            {
                "dimension_id": dimension_id,
                "title": str(definition.get("title", "")).strip(),
                "priority_rank": int(definition.get("priority_rank", 100) or 100),
                "priority_level": str(definition.get("priority_level", "low")).strip() or "low",
                "state": state,
                "dimension_rationale": rationale,
                "dimension_definition_rationale": str(
                    definition.get("dimension_rationale", "")
                ).strip(),
                "current_objective_class": current_objective_class,
                "related_objective_class": str(
                    definition.get("objective_class", "")
                ).strip(),
                "related_objective_title": _objective_title_for_quality_dimension(definition),
                "related_skill_pack_id": skill_pack_id,
                "required_relative_paths": required_relative_paths,
                "missing_relative_paths": missing_relative_paths,
                "evidence_rows": evidence_rows,
                "resolution_marker_relative_paths": marker_relative_paths,
                "marker_rows": marker_rows,
                "requires_recorded_pack_resolution": bool(
                    definition.get("requires_recorded_pack_resolution", False)
                ),
                "reference_target_id": str(
                    reference_target_context.get("active_bounded_reference_target_id", "")
                ).strip()
                or str(
                    reference_target_context.get(
                        "protected_live_baseline_reference_id", ""
                    )
                ).strip(),
                "reference_target_consumption_state": str(
                    reference_target_context.get("consumption_state", "")
                ).strip(),
                "comparison_basis": str(
                    reference_target_context.get("comparison_basis", "")
                ).strip(),
                "improved_relative_to_reference_target": improved_relative,
                "last_completed_skill_pack_id": last_completed_skill_pack_id,
                "last_completed_skill_pack_title": last_completed_skill_pack_title,
                "last_improvement_state": last_improvement_state,
                "last_quality_gap_id": last_quality_gap_id,
                "current_pack_completed": current_pack_completed,
                "resolved_by_marker": resolved_by_marker,
            }
        )

    dimension_rows.sort(
        key=lambda item: (
            int(item.get("priority_rank", 100) or 100),
            str(item.get("dimension_id", "")),
        )
    )

    candidate_rows = [
        dict(item)
        for item in dimension_rows
        if str(item.get("state", "")).strip() != QUALITY_DIMENSION_RESOLVED_STATE
        and str(item.get("related_skill_pack_id", "")).strip()
        and str(item.get("related_objective_class", "")).strip()
    ]
    latest_completed_skill_pack_id = str(latest_skill_pack_id).strip()
    selected_candidate = dict(candidate_rows[0]) if candidate_rows else {}
    avoided_repeating_last_pack = False
    if (
        len(candidate_rows) > 1
        and latest_completed_skill_pack_id
        and str(selected_candidate.get("related_skill_pack_id", "")).strip()
        == latest_completed_skill_pack_id
    ):
        for row in candidate_rows[1:]:
            if str(row.get("related_skill_pack_id", "")).strip() != latest_completed_skill_pack_id:
                selected_candidate = dict(row)
                avoided_repeating_last_pack = True
                break

    resolved_rows = [
        item for item in dimension_rows if str(item.get("state", "")).strip() == QUALITY_DIMENSION_RESOLVED_STATE
    ]
    improved_rows = [
        item for item in resolved_rows if bool(item.get("improved_relative_to_reference_target", False))
    ]
    partial_rows = [
        item for item in dimension_rows if str(item.get("state", "")).strip() == QUALITY_DIMENSION_PARTIAL_STATE
    ]
    weak_rows = [
        item for item in dimension_rows if str(item.get("state", "")).strip() == QUALITY_DIMENSION_WEAK_STATE
    ]
    if len(improved_rows) >= 2:
        composite_state = QUALITY_COMPOSITE_MULTI_DIMENSION_STATE
    elif improved_rows:
        composite_state = QUALITY_COMPOSITE_SINGLE_DIMENSION_STATE
    else:
        composite_state = QUALITY_COMPOSITE_NOT_YET_STRONGER_STATE

    priority_matrix = {
        "schema_name": SUCCESSOR_QUALITY_PRIORITY_MATRIX_SCHEMA_NAME,
        "schema_version": SUCCESSOR_QUALITY_PRIORITY_MATRIX_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(current_objective.get("objective_id", "")).strip()
        or str(workspace_root.name),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "active_bounded_reference_target_id": str(
            reference_target_context.get("active_bounded_reference_target_id", "")
        ).strip(),
        "protected_live_baseline_reference_id": str(
            reference_target_context.get("protected_live_baseline_reference_id", "")
        ).strip(),
        "candidate_dimensions": candidate_rows,
        "weakest_dimension_id": str(selected_candidate.get("dimension_id", "")).strip(),
        "weakest_dimension_title": str(selected_candidate.get("title", "")).strip(),
    }
    next_pack_plan = {
        "schema_name": SUCCESSOR_QUALITY_NEXT_PACK_PLAN_SCHEMA_NAME,
        "schema_version": SUCCESSOR_QUALITY_NEXT_PACK_PLAN_SCHEMA_VERSION,
        "generated_at": _now(),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "active_bounded_reference_target_id": str(
            reference_target_context.get("active_bounded_reference_target_id", "")
        ).strip(),
        "reference_target_consumption_state": str(
            reference_target_context.get("consumption_state", "")
        ).strip(),
        "selected_dimension_id": str(selected_candidate.get("dimension_id", "")).strip(),
        "selected_dimension_title": str(selected_candidate.get("title", "")).strip(),
        "selected_priority_level": str(selected_candidate.get("priority_level", "")).strip(),
        "selected_objective_class": str(
            selected_candidate.get("related_objective_class", "")
        ).strip(),
        "selected_objective_id": str(
            selected_candidate.get("related_objective_class", "")
        ).strip(),
        "selected_objective_title": str(
            selected_candidate.get("related_objective_title", "")
        ).strip(),
        "selected_skill_pack_id": str(
            selected_candidate.get("related_skill_pack_id", "")
        ).strip(),
        "selected_rationale": (
            "The next bounded quality-improvement pack targets the highest-priority unresolved dimension."
            if selected_candidate
            else "No additional bounded quality-improvement pack is currently recommended."
        ),
        "avoided_repeating_last_skill_pack": avoided_repeating_last_pack,
        "last_completed_skill_pack_id": latest_completed_skill_pack_id,
        "alternative_dimensions": [
            {
                "dimension_id": str(item.get("dimension_id", "")).strip(),
                "title": str(item.get("title", "")).strip(),
                "priority_level": str(item.get("priority_level", "")).strip(),
                "related_objective_class": str(item.get("related_objective_class", "")).strip(),
                "related_skill_pack_id": str(item.get("related_skill_pack_id", "")).strip(),
            }
            for item in candidate_rows[1:]
        ],
    }
    composite_evaluation = {
        "schema_name": SUCCESSOR_QUALITY_COMPOSITE_EVALUATION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_QUALITY_COMPOSITE_EVALUATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "active_bounded_reference_target_id": str(
            reference_target_context.get("active_bounded_reference_target_id", "")
        ).strip(),
        "reference_target_consumption_state": str(
            reference_target_context.get("consumption_state", "")
        ).strip(),
        "protected_live_baseline_reference_id": str(
            reference_target_context.get("protected_live_baseline_reference_id", "")
        ).strip(),
        "comparison_basis": str(
            reference_target_context.get("comparison_basis", "")
        ).strip(),
        "composite_quality_state": composite_state,
        "materially_stronger_than_reference_target_in_aggregate": len(improved_rows) >= 2,
        "resolved_dimension_ids": [
            str(item.get("dimension_id", "")).strip() for item in resolved_rows
        ],
        "improved_dimension_ids": [
            str(item.get("dimension_id", "")).strip() for item in improved_rows
        ],
        "partial_dimension_ids": [
            str(item.get("dimension_id", "")).strip() for item in partial_rows
        ],
        "weak_dimension_ids": [
            str(item.get("dimension_id", "")).strip() for item in weak_rows
        ],
        "resolved_dimension_count": len(resolved_rows),
        "improved_dimension_count": len(improved_rows),
        "partial_dimension_count": len(partial_rows),
        "weak_dimension_count": len(weak_rows),
        "aggregate_rationale": (
            "Multiple bounded quality dimensions now record explicit improvements relative to the admitted-candidate reference target."
            if len(improved_rows) >= 2
            else (
                "One bounded quality dimension now records a stronger successor relative to the admitted-candidate reference target, but more dimensions remain weak."
                if improved_rows
                else "The successor is not yet materially stronger in aggregate relative to the admitted-candidate reference target."
            )
        ),
    }
    roadmap_payload = {
        "schema_name": SUCCESSOR_QUALITY_ROADMAP_SCHEMA_NAME,
        "schema_version": SUCCESSOR_QUALITY_ROADMAP_SCHEMA_VERSION,
        "generated_at": _now(),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_objective_id": str(current_objective.get("objective_id", "")).strip(),
        "current_objective_class": str(current_objective.get("objective_class", "")).strip(),
        "current_objective_source_kind": str(current_objective.get("source_kind", "")).strip(),
        "active_bounded_reference_target_id": str(
            reference_target_context.get("active_bounded_reference_target_id", "")
        ).strip(),
        "reference_target_consumption_state": str(
            reference_target_context.get("consumption_state", "")
        ).strip(),
        "protected_live_baseline_reference_id": str(
            reference_target_context.get("protected_live_baseline_reference_id", "")
        ).strip(),
        "comparison_basis": str(
            reference_target_context.get("comparison_basis", "")
        ).strip(),
        "tracked_dimensions": dimension_rows,
        "known_gap_dimension_ids": [
            str(item.get("dimension_id", "")).strip()
            for item in candidate_rows
        ],
        "recommended_next_pack_plan": next_pack_plan,
        "composite_quality_state": composite_state,
        "materially_stronger_than_reference_target_in_aggregate": len(improved_rows) >= 2,
        "evidence_used": {
            "reference_target_consumption_path": str(paths["reference_target_consumption_path"]),
            "skill_pack_invocation_path": str(paths["skill_pack_invocation_path"]),
            "skill_pack_result_path": str(paths["skill_pack_result_path"]),
            "quality_gap_summary_path": str(paths["quality_gap_summary_path"]),
            "quality_improvement_summary_path": str(paths["quality_improvement_summary_path"]),
        },
    }
    return {
        "roadmap": roadmap_payload,
        "priority_matrix": priority_matrix,
        "composite_evaluation": composite_evaluation,
        "next_pack_plan": next_pack_plan,
    }


def _materialize_successor_quality_roadmap_outputs(
    *,
    workspace_root: Path,
    current_objective: dict[str, Any],
    reference_target_context: dict[str, Any],
    latest_skill_pack_invocation: dict[str, Any],
    latest_skill_pack_result: dict[str, Any],
    latest_quality_gap_summary: dict[str, Any],
    latest_quality_improvement_summary: dict[str, Any],
    runtime_event_log_path: Path | None = None,
    session_id: str = "",
    directive_id: str = "",
    execution_profile: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    outputs = _evaluate_successor_quality_roadmap_state(
        workspace_root=workspace_root,
        current_objective=current_objective,
        reference_target_context=reference_target_context,
        latest_skill_pack_invocation=latest_skill_pack_invocation,
        latest_skill_pack_result=latest_skill_pack_result,
        latest_quality_gap_summary=latest_quality_gap_summary,
        latest_quality_improvement_summary=latest_quality_improvement_summary,
    )
    write_rows = [
        (paths["quality_roadmap_path"], dict(outputs.get("roadmap", {})), "successor_quality_roadmap_json"),
        (
            paths["quality_priority_matrix_path"],
            dict(outputs.get("priority_matrix", {})),
            "successor_quality_priority_matrix_json",
        ),
        (
            paths["quality_composite_evaluation_path"],
            dict(outputs.get("composite_evaluation", {})),
            "successor_quality_composite_evaluation_json",
        ),
        (
            paths["quality_next_pack_plan_path"],
            dict(outputs.get("next_pack_plan", {})),
            "successor_quality_next_pack_plan_json",
        ),
    ]
    if runtime_event_log_path and str(runtime_event_log_path) not in {"", "."}:
        for artifact_path, artifact_payload, artifact_kind in write_rows:
            _write_json(
                artifact_path,
                artifact_payload,
                log_path=runtime_event_log_path,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=workspace_id,
                workspace_root=str(workspace_root),
                work_item_id="successor_quality_roadmap",
                artifact_kind=artifact_kind,
            )
        _event(
            runtime_event_log_path,
            event_type="successor_quality_roadmap_recorded",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            composite_quality_state=str(
                dict(outputs.get("composite_evaluation", {})).get(
                    "composite_quality_state", ""
                )
            ),
            materially_stronger_than_reference_target_in_aggregate=bool(
                dict(outputs.get("composite_evaluation", {})).get(
                    "materially_stronger_than_reference_target_in_aggregate",
                    False,
                )
            ),
            selected_next_skill_pack_id=str(
                dict(outputs.get("next_pack_plan", {})).get(
                    "selected_skill_pack_id", ""
                )
            ),
            selected_next_objective_class=str(
                dict(outputs.get("next_pack_plan", {})).get(
                    "selected_objective_class", ""
                )
            ),
            quality_roadmap_path=str(paths["quality_roadmap_path"]),
        )
    else:
        for artifact_path, artifact_payload, _artifact_kind in write_rows:
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")
    return {
        **outputs,
        "roadmap_path": str(paths["quality_roadmap_path"]),
        "priority_matrix_path": str(paths["quality_priority_matrix_path"]),
        "composite_evaluation_path": str(paths["quality_composite_evaluation_path"]),
        "next_pack_plan_path": str(paths["quality_next_pack_plan_path"]),
    }


def _quality_composite_rank(state: str) -> int:
    normalized = str(state or "").strip()
    return {
        QUALITY_COMPOSITE_NOT_YET_STRONGER_STATE: 0,
        QUALITY_COMPOSITE_SINGLE_DIMENSION_STATE: 1,
        QUALITY_COMPOSITE_MULTI_DIMENSION_STATE: 2,
    }.get(normalized, -1)


def _synthesized_prior_generation_row(
    *,
    generation_index: int,
    prior_candidate_id: str,
    directive_id: str,
    workspace_root: Path,
    protected_live_baseline_reference_id: str,
) -> dict[str, Any]:
    return {
        "generation_index": int(generation_index),
        "admitted_candidate_id": prior_candidate_id,
        "candidate_bundle_identity": _humanize_objective_id(prior_candidate_id),
        "candidate_variant": "historical_lineage_reference",
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "quality_composite_state": "historical_reference_from_lineage",
        "materially_stronger_in_aggregate": False,
        "improved_dimension_ids": [],
        "weak_dimension_ids": [],
        "reference_target_id": prior_candidate_id,
        "protected_live_baseline_reference_id": protected_live_baseline_reference_id,
        "record_source": "lineage_reconstruction",
        "generation_rationale": (
            "This prior admitted candidate row is reconstructed conservatively from revised-candidate lineage so the current generation can be compared explicitly without mutating any protected/live baseline state."
        ),
    }


def _evaluate_successor_generation_progress_state(
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    admitted_candidate = load_json(paths["admitted_candidate_path"])
    reference_target = load_json(paths["reference_target_path"])
    reference_target_consumption = load_json(paths["reference_target_consumption_path"])
    revised_candidate_bundle = load_json(paths["revised_candidate_bundle_path"])
    revised_candidate_comparison = load_json(paths["revised_candidate_comparison_path"])
    revised_candidate_promotion_summary = load_json(
        paths["revised_candidate_promotion_summary_path"]
    )
    skill_pack_invocation = load_json(paths["skill_pack_invocation_path"])
    skill_pack_result = load_json(paths["skill_pack_result_path"])
    quality_roadmap = load_json(paths["quality_roadmap_path"])
    quality_priority_matrix = load_json(paths["quality_priority_matrix_path"])
    quality_composite_evaluation = load_json(paths["quality_composite_evaluation_path"])
    quality_next_pack_plan = load_json(paths["quality_next_pack_plan_path"])
    existing_history = load_json(paths["generation_history_path"])

    current_admitted_candidate_id = str(
        admitted_candidate.get("admitted_candidate_id", "")
    ).strip() or str(reference_target.get("preferred_reference_target_id", "")).strip()
    if not current_admitted_candidate_id:
        return {}

    directive_id = str(admitted_candidate.get("directive_id", "")).strip() or str(
        reference_target.get("directive_id", "")
    ).strip()
    protected_live_baseline_reference_id = str(
        reference_target_consumption.get("protected_live_baseline_reference_id", "")
    ).strip() or str(
        reference_target.get("protected_live_baseline_reference_id", "")
    ).strip() or "current_bounded_baseline_expectations_v1"
    # Once a future revised-candidate bundle is staged, it may already point at the
    # next pending revision. Generation-progress comparison for the current admitted
    # target must stay anchored to the admitted/reference-target lineage first.
    prior_admitted_candidate_id = str(
        admitted_candidate.get("prior_admitted_candidate_id", "")
    ).strip() or str(reference_target.get("supersedes_reference_target_id", "")).strip() or str(
        reference_target.get("prior_reference_target_id", "")
    ).strip() or str(
        revised_candidate_bundle.get("prior_admitted_candidate_id", "")
    ).strip()

    comparison_improved_dimension_ids = _unique_string_list(
        list(revised_candidate_comparison.get("improved_dimension_ids", []))
    )
    comparison_weak_dimension_ids = _unique_string_list(
        list(revised_candidate_comparison.get("remaining_weak_dimension_ids", []))
    )
    composite_improved_dimension_ids = _unique_string_list(
        list(quality_composite_evaluation.get("improved_dimension_ids", []))
    )
    composite_weak_dimension_ids = _unique_string_list(
        list(quality_composite_evaluation.get("weak_dimension_ids", []))
    )
    latest_reference_target_context = dict(
        skill_pack_result.get("reference_target_context", {})
    )
    if not latest_reference_target_context:
        latest_reference_target_context = dict(
            skill_pack_invocation.get("reference_target_context", {})
        )
    latest_result_reference_target_id = str(
        latest_reference_target_context.get("active_bounded_reference_target_id", "")
    ).strip()
    latest_result_matches_current_admitted_candidate = bool(
        latest_result_reference_target_id
        and latest_result_reference_target_id == current_admitted_candidate_id
        and str(skill_pack_result.get("result_state", "")).strip() == "complete"
        and not bool(skill_pack_result.get("protected_surface_mutation_attempted", False))
        and bool(skill_pack_result.get("outputs_within_workspace", True))
    )
    current_generation_improved_dimension_ids = _unique_string_list(
        comparison_improved_dimension_ids + composite_improved_dimension_ids
    )
    current_generation_weak_dimension_ids = (
        list(composite_weak_dimension_ids)
        if latest_result_matches_current_admitted_candidate
        else _unique_string_list(
            comparison_weak_dimension_ids or composite_weak_dimension_ids
        )
    )

    current_generation_row = {
        "generation_index": 0,
        "admitted_candidate_id": current_admitted_candidate_id,
        "candidate_bundle_identity": str(
            admitted_candidate.get("candidate_bundle_identity", "")
        ).strip()
        or str(revised_candidate_bundle.get("candidate_bundle_identity", "")).strip()
        or _humanize_objective_id(current_admitted_candidate_id),
        "candidate_variant": (
            "revised_candidate"
            if str(revised_candidate_bundle.get("revised_candidate_id", "")).strip()
            and str(revised_candidate_promotion_summary.get("reference_target_rollover_state", "")).strip()
            == "rolled_forward_to_revised_candidate"
            else "candidate_promotion_bundle"
        ),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "revised_candidate_id": str(
            revised_candidate_bundle.get("revised_candidate_id", "")
        ).strip(),
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "quality_composite_state": str(
            quality_composite_evaluation.get("composite_quality_state", "")
        ).strip(),
        "materially_stronger_in_aggregate": bool(
            revised_candidate_comparison.get(
                "materially_stronger_than_prior_admitted_candidate_in_aggregate",
                False,
            )
            or quality_composite_evaluation.get(
                "materially_stronger_than_reference_target_in_aggregate",
                False,
            )
        ),
        "improved_dimension_ids": list(current_generation_improved_dimension_ids),
        "weak_dimension_ids": list(current_generation_weak_dimension_ids),
        "reference_target_id": str(
            reference_target.get("preferred_reference_target_id", "")
        ).strip()
        or current_admitted_candidate_id,
        "reference_target_rollover_state": str(
            revised_candidate_promotion_summary.get("reference_target_rollover_state", "")
        ).strip()
        or str(reference_target.get("reference_target_rollover_state", "")).strip(),
        "reference_target_consumption_state": str(
            reference_target_consumption.get("consumption_state", "")
        ).strip(),
        "protected_live_baseline_reference_id": protected_live_baseline_reference_id,
        "record_source": "current_admitted_candidate_artifacts",
        "generation_rationale": (
            "This generation row records the currently admitted bounded reference candidate and its composite quality delta relative to the prior admitted candidate in the same bounded lineage."
        ),
    }

    existing_rows: list[dict[str, Any]] = []
    for item in list(existing_history.get("generations", [])):
        row = dict(item)
        candidate_id = str(row.get("admitted_candidate_id", "")).strip()
        if candidate_id:
            existing_rows.append(row)
    existing_rows.sort(key=lambda item: int(item.get("generation_index", 0) or 0))
    rows_by_candidate_id = {
        str(item.get("admitted_candidate_id", "")).strip(): dict(item)
        for item in existing_rows
        if str(item.get("admitted_candidate_id", "")).strip()
    }

    generations: list[dict[str, Any]] = list(existing_rows)
    if not generations and prior_admitted_candidate_id and (
        prior_admitted_candidate_id != current_admitted_candidate_id
    ):
        generations.append(
            _synthesized_prior_generation_row(
                generation_index=1,
                prior_candidate_id=prior_admitted_candidate_id,
                directive_id=directive_id,
                workspace_root=workspace_root,
                protected_live_baseline_reference_id=protected_live_baseline_reference_id,
            )
        )
        rows_by_candidate_id[prior_admitted_candidate_id] = dict(generations[0])

    existing_current_row = rows_by_candidate_id.get(current_admitted_candidate_id, {})
    if existing_current_row:
        current_generation_index = int(
            existing_current_row.get("generation_index", 0) or 0
        )
    else:
        current_generation_index = (
            max(
                [
                    int(item.get("generation_index", 0) or 0)
                    for item in generations
                ]
                or [0]
            )
            + 1
        )
    current_generation_row["generation_index"] = current_generation_index

    if existing_current_row:
        merged_row = dict(existing_current_row)
        merged_row.update(current_generation_row)
        for index, item in enumerate(generations):
            if (
                str(item.get("admitted_candidate_id", "")).strip()
                == current_admitted_candidate_id
            ):
                generations[index] = merged_row
                break
        current_generation_row = merged_row
    else:
        generations.append(current_generation_row)
    generations.sort(key=lambda item: int(item.get("generation_index", 0) or 0))

    prior_generation_row = {}
    if prior_admitted_candidate_id:
        prior_generation_row = next(
            (
                dict(item)
                for item in generations
                if str(item.get("admitted_candidate_id", "")).strip()
                == prior_admitted_candidate_id
            ),
            {},
        )
    if not prior_generation_row:
        prior_generation_row = next(
            (
                dict(item)
                for item in reversed(generations)
                if int(item.get("generation_index", 0) or 0) < current_generation_index
            ),
            {},
        )

    current_improved = set(
        _unique_string_list(list(current_generation_row.get("improved_dimension_ids", [])))
    )
    current_weak = set(
        _unique_string_list(list(current_generation_row.get("weak_dimension_ids", [])))
    )
    prior_improved = set(
        _unique_string_list(list(prior_generation_row.get("improved_dimension_ids", [])))
    )
    prior_weak = set(
        _unique_string_list(list(prior_generation_row.get("weak_dimension_ids", [])))
    )
    newly_improved_dimension_ids = sorted(
        current_improved - prior_improved if prior_generation_row else current_improved
    )
    regressed_dimension_ids = sorted(prior_improved.intersection(current_weak))
    persistent_weak_dimension_ids = sorted(prior_weak.intersection(current_weak))
    current_rank = _quality_composite_rank(
        str(current_generation_row.get("quality_composite_state", "")).strip()
    )
    prior_rank = _quality_composite_rank(
        str(prior_generation_row.get("quality_composite_state", "")).strip()
    )
    materially_stronger_vs_prior = bool(
        revised_candidate_comparison.get(
            "materially_stronger_than_prior_admitted_candidate_in_aggregate",
            current_generation_row.get("materially_stronger_in_aggregate", False),
        )
    )

    if regressed_dimension_ids and newly_improved_dimension_ids:
        progress_state = GENERATIONAL_CHURN_DETECTED_STATE
        progress_rationale = (
            "This generation records both new improvements and important weak areas that overlap with prior improved dimensions, so the lineage currently looks churny rather than stably stronger."
        )
    elif regressed_dimension_ids or current_rank < prior_rank:
        progress_state = GENERATIONAL_REGRESSION_DETECTED_STATE
        progress_rationale = (
            "This generation is weaker than the prior admitted candidate on one or more important bounded quality dimensions."
        )
    elif materially_stronger_vs_prior and newly_improved_dimension_ids:
        progress_state = GENERATIONAL_IMPROVEMENT_CONFIRMED_STATE
        progress_rationale = (
            "This generation records explicit multi-dimension bounded gains relative to the prior admitted candidate."
        )
    elif newly_improved_dimension_ids:
        progress_state = GENERATIONAL_IMPROVEMENT_PARTIAL_STATE
        progress_rationale = (
            "This generation records bounded gains on some dimensions, but aggregate movement is not yet strong enough to treat the overall lineage as decisively improved."
        )
    else:
        progress_state = GENERATIONAL_STAGNATION_DETECTED_STATE
        progress_rationale = (
            "This generation does not yet record meaningful new bounded improvement relative to the prior admitted candidate."
        )

    selected_objective_id = str(
        quality_next_pack_plan.get("selected_objective_id", "")
    ).strip()
    selected_objective_class = str(
        quality_next_pack_plan.get("selected_objective_class", "")
    ).strip()
    selected_skill_pack_id = str(
        quality_next_pack_plan.get("selected_skill_pack_id", "")
    ).strip()
    selected_dimension_id = str(
        quality_next_pack_plan.get("selected_dimension_id", "")
    ).strip()
    weak_dimension_ids = sorted(current_weak)

    if progress_state == GENERATIONAL_IMPROVEMENT_CONFIRMED_STATE:
        if weak_dimension_ids and selected_objective_id:
            recommendation_state = PROGRESS_RECOMMENDATION_CONTINUE_STATE
            additional_bounded_improvement_justified = True
            recommendation_rationale = (
                "This generation is materially stronger than the prior admitted candidate, and additional bounded quality dimensions remain weak enough to justify another conservative improvement cycle."
            )
        else:
            recommendation_state = PROGRESS_RECOMMENDATION_HOLD_STATE
            additional_bounded_improvement_justified = False
            recommendation_rationale = (
                "This generation is materially stronger and no higher-value bounded follow-on is currently required, so the current reference target should be held."
            )
    elif progress_state == GENERATIONAL_IMPROVEMENT_PARTIAL_STATE:
        recommendation_state = PROGRESS_RECOMMENDATION_REMEDIATE_STATE
        additional_bounded_improvement_justified = bool(
            selected_objective_id or weak_dimension_ids
        )
        recommendation_rationale = (
            "Some bounded quality dimensions improved, but the lineage still needs targeted remediation before another revised-candidate cycle would be justified."
        )
    elif progress_state == GENERATIONAL_STAGNATION_DETECTED_STATE:
        recommendation_state = PROGRESS_RECOMMENDATION_PAUSE_STATE
        additional_bounded_improvement_justified = False
        recommendation_rationale = (
            "The lineage currently appears plateaued, so NOVALI should pause for explicit operator review before attempting another revised-candidate cycle."
        )
    elif progress_state == GENERATIONAL_CHURN_DETECTED_STATE:
        recommendation_state = PROGRESS_RECOMMENDATION_PAUSE_STATE
        additional_bounded_improvement_justified = False
        recommendation_rationale = (
            "The lineage currently records movement without stable multi-dimension gain, so additional bounded improvement should pause pending operator review."
        )
    else:
        recommendation_state = PROGRESS_RECOMMENDATION_ESCALATE_STATE
        additional_bounded_improvement_justified = False
        recommendation_rationale = (
            "The lineage currently records regression against the prior admitted candidate, so the safer posture is to escalate for explicit candidate review."
        )

    generation_delta = {
        "schema_name": SUCCESSOR_GENERATION_DELTA_SCHEMA_NAME,
        "schema_version": SUCCESSOR_GENERATION_DELTA_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_generation_index": int(current_generation_index),
        "prior_generation_index": int(
            prior_generation_row.get("generation_index", 0) or 0
        ),
        "current_admitted_candidate_id": current_admitted_candidate_id,
        "prior_admitted_candidate_id": str(
            prior_generation_row.get("admitted_candidate_id", "")
        ).strip()
        or prior_admitted_candidate_id,
        "current_candidate_bundle_identity": str(
            current_generation_row.get("candidate_bundle_identity", "")
        ).strip(),
        "prior_candidate_bundle_identity": str(
            prior_generation_row.get("candidate_bundle_identity", "")
        ).strip(),
        "current_quality_composite_state": str(
            current_generation_row.get("quality_composite_state", "")
        ).strip(),
        "prior_quality_composite_state": str(
            prior_generation_row.get("quality_composite_state", "")
        ).strip(),
        "current_materially_stronger_in_aggregate": bool(
            current_generation_row.get("materially_stronger_in_aggregate", False)
        ),
        "materially_stronger_than_prior_admitted_candidate_in_aggregate": materially_stronger_vs_prior,
        "newly_improved_dimension_ids": newly_improved_dimension_ids,
        "persistent_weak_dimension_ids": persistent_weak_dimension_ids,
        "regressed_dimension_ids": regressed_dimension_ids,
        "current_weak_dimension_ids": weak_dimension_ids,
        "progress_state": progress_state,
        "comparison_rationale": progress_rationale,
        "comparison_artifact_path": str(paths["revised_candidate_comparison_path"]),
        "quality_composite_evaluation_path": str(
            paths["quality_composite_evaluation_path"]
        ),
    }

    generation_history = {
        "schema_name": SUCCESSOR_GENERATION_HISTORY_SCHEMA_NAME,
        "schema_version": SUCCESSOR_GENERATION_HISTORY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_generation_index": int(current_generation_index),
        "current_admitted_candidate_id": current_admitted_candidate_id,
        "prior_admitted_candidate_id": str(
            generation_delta.get("prior_admitted_candidate_id", "")
        ),
        "preferred_reference_target_id": str(
            reference_target.get("preferred_reference_target_id", "")
        ).strip(),
        "protected_live_baseline_reference_id": protected_live_baseline_reference_id,
        "generations": generations,
    }

    progress_governance = {
        "schema_name": SUCCESSOR_PROGRESS_GOVERNANCE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_PROGRESS_GOVERNANCE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_generation_index": int(current_generation_index),
        "current_admitted_candidate_id": current_admitted_candidate_id,
        "prior_admitted_candidate_id": str(
            generation_delta.get("prior_admitted_candidate_id", "")
        ),
        "progress_state": progress_state,
        "additional_bounded_improvement_justified": additional_bounded_improvement_justified,
        "current_weak_dimension_ids": weak_dimension_ids,
        "newly_improved_dimension_ids": newly_improved_dimension_ids,
        "persistent_weak_dimension_ids": persistent_weak_dimension_ids,
        "regressed_dimension_ids": regressed_dimension_ids,
        "history_length": len(generations),
        "progress_rationale": progress_rationale,
        "evidence_used": {
            "generation_history_path": str(paths["generation_history_path"]),
            "generation_delta_path": str(paths["generation_delta_path"]),
            "reference_target_path": str(paths["reference_target_path"]),
            "reference_target_consumption_path": str(
                paths["reference_target_consumption_path"]
            ),
            "revised_candidate_bundle_path": str(paths["revised_candidate_bundle_path"]),
            "revised_candidate_comparison_path": str(
                paths["revised_candidate_comparison_path"]
            ),
            "quality_roadmap_path": str(paths["quality_roadmap_path"]),
            "quality_composite_evaluation_path": str(
                paths["quality_composite_evaluation_path"]
            ),
        },
    }

    progress_recommendation = {
        "schema_name": SUCCESSOR_PROGRESS_RECOMMENDATION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_PROGRESS_RECOMMENDATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_generation_index": int(current_generation_index),
        "current_admitted_candidate_id": current_admitted_candidate_id,
        "prior_admitted_candidate_id": str(
            generation_delta.get("prior_admitted_candidate_id", "")
        ),
        "progress_state": progress_state,
        "recommendation_state": recommendation_state,
        "additional_bounded_improvement_justified": additional_bounded_improvement_justified,
        "recommended_objective_id": selected_objective_id,
        "recommended_objective_class": selected_objective_class
        or _objective_class_from_objective_id(selected_objective_id),
        "recommended_skill_pack_id": selected_skill_pack_id,
        "recommended_dimension_id": selected_dimension_id,
        "recommended_dimension_title": str(
            quality_next_pack_plan.get("selected_dimension_title", "")
        ).strip()
        or str(quality_priority_matrix.get("weakest_dimension_title", "")).strip(),
        "target_dimension_ids": weak_dimension_ids,
        "operator_review_required": recommendation_state
        in {
            PROGRESS_RECOMMENDATION_PAUSE_STATE,
            PROGRESS_RECOMMENDATION_ESCALATE_STATE,
        },
        "remediation_required": recommendation_state
        in {
            PROGRESS_RECOMMENDATION_REMEDIATE_STATE,
            PROGRESS_RECOMMENDATION_PAUSE_STATE,
            PROGRESS_RECOMMENDATION_ESCALATE_STATE,
        },
        "reference_target_rollover_state": str(
            revised_candidate_promotion_summary.get("reference_target_rollover_state", "")
        ).strip(),
        "hold_current_reference_target": recommendation_state
        == PROGRESS_RECOMMENDATION_HOLD_STATE,
        "baseline_mutation_performed": False,
        "rationale": recommendation_rationale,
        "quality_roadmap_path": str(paths["quality_roadmap_path"]),
        "quality_next_pack_plan_path": str(paths["quality_next_pack_plan_path"]),
    }
    return {
        "generation_history": generation_history,
        "generation_delta": generation_delta,
        "progress_governance": progress_governance,
        "progress_recommendation": progress_recommendation,
    }


def _materialize_successor_generation_progress_outputs(
    *,
    workspace_root: Path,
    runtime_event_log_path: Path | None = None,
    session_id: str = "",
    directive_id: str = "",
    execution_profile: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    outputs = _evaluate_successor_generation_progress_state(workspace_root=workspace_root)
    if not outputs:
        return {
            "generation_history": load_json(paths["generation_history_path"]),
            "generation_delta": load_json(paths["generation_delta_path"]),
            "progress_governance": load_json(paths["progress_governance_path"]),
            "progress_recommendation": load_json(paths["progress_recommendation_path"]),
            "generation_history_path": str(paths["generation_history_path"]),
            "generation_delta_path": str(paths["generation_delta_path"]),
            "progress_governance_path": str(paths["progress_governance_path"]),
            "progress_recommendation_path": str(paths["progress_recommendation_path"]),
        }

    write_rows = [
        (
            paths["generation_history_path"],
            dict(outputs.get("generation_history", {})),
            "successor_generation_history_json",
        ),
        (
            paths["generation_delta_path"],
            dict(outputs.get("generation_delta", {})),
            "successor_generation_delta_json",
        ),
        (
            paths["progress_governance_path"],
            dict(outputs.get("progress_governance", {})),
            "successor_progress_governance_json",
        ),
        (
            paths["progress_recommendation_path"],
            dict(outputs.get("progress_recommendation", {})),
            "successor_progress_recommendation_json",
        ),
    ]
    if runtime_event_log_path and str(runtime_event_log_path) not in {"", "."}:
        for artifact_path, artifact_payload, artifact_kind in write_rows:
            _write_json(
                artifact_path,
                artifact_payload,
                log_path=runtime_event_log_path,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=workspace_id,
                workspace_root=str(workspace_root),
                work_item_id="successor_generation_progress",
                artifact_kind=artifact_kind,
            )
        _event(
            runtime_event_log_path,
            event_type="successor_generation_progress_recorded",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            generation_index=int(
                dict(outputs.get("generation_history", {})).get(
                    "current_generation_index", 0
                )
                or 0
            ),
            current_admitted_candidate_id=str(
                dict(outputs.get("generation_delta", {})).get(
                    "current_admitted_candidate_id", ""
                )
            ),
            prior_admitted_candidate_id=str(
                dict(outputs.get("generation_delta", {})).get(
                    "prior_admitted_candidate_id", ""
                )
            ),
            progress_state=str(
                dict(outputs.get("progress_governance", {})).get("progress_state", "")
            ),
            progress_recommendation_state=str(
                dict(outputs.get("progress_recommendation", {})).get(
                    "recommendation_state", ""
                )
            ),
            progress_recommendation_path=str(paths["progress_recommendation_path"]),
        )
    else:
        for artifact_path, artifact_payload, _artifact_kind in write_rows:
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    _sync_generation_progress_to_latest_artifacts(
        workspace_root=workspace_root,
        paths=paths,
        generation_history=dict(outputs.get("generation_history", {})),
        generation_delta=dict(outputs.get("generation_delta", {})),
        progress_governance=dict(outputs.get("progress_governance", {})),
        progress_recommendation=dict(outputs.get("progress_recommendation", {})),
    )
    return {
        **outputs,
        "generation_history_path": str(paths["generation_history_path"]),
        "generation_delta_path": str(paths["generation_delta_path"]),
        "progress_governance_path": str(paths["progress_governance_path"]),
        "progress_recommendation_path": str(paths["progress_recommendation_path"]),
    }


def _strategy_title(strategy_state: str) -> str:
    normalized = str(strategy_state or "").strip()
    return {
        STRATEGY_CONTINUE_REFINING_CURRENT_REFERENCE_TARGET_STATE: "Continue refining current reference target",
        STRATEGY_OPEN_TARGETED_REMEDIATION_WAVE_STATE: "Open targeted remediation wave",
        STRATEGY_START_NEXT_QUALITY_WAVE_STATE: "Start next quality wave",
        STRATEGY_PAUSE_FOR_OPERATOR_REVIEW_STATE: "Pause for operator review",
        STRATEGY_HOLD_CURRENT_REFERENCE_TARGET_STATE: "Hold current reference target",
        STRATEGY_HOLD_AND_OBSERVE_BEFORE_FURTHER_CHANGE_STATE: "Hold and observe before further change",
    }.get(normalized, _humanize_objective_id(normalized) or "Unspecified strategy")


def _evaluate_successor_strategy_selection_state(
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    generation_history = load_json(paths["generation_history_path"])
    generation_delta = load_json(paths["generation_delta_path"])
    progress_governance = load_json(paths["progress_governance_path"])
    progress_recommendation = load_json(paths["progress_recommendation_path"])
    quality_roadmap = load_json(paths["quality_roadmap_path"])
    quality_priority_matrix = load_json(paths["quality_priority_matrix_path"])
    quality_composite_evaluation = load_json(paths["quality_composite_evaluation_path"])
    quality_next_pack_plan = load_json(paths["quality_next_pack_plan_path"])
    reference_target = load_json(paths["reference_target_path"])
    reference_target_consumption = load_json(paths["reference_target_consumption_path"])

    current_generation_index = int(
        generation_history.get("current_generation_index", 0) or 0
    )
    current_reference_target_id = str(
        reference_target.get("preferred_reference_target_id", "")
    ).strip() or str(
        reference_target_consumption.get("active_bounded_reference_target_id", "")
    ).strip() or str(generation_delta.get("current_admitted_candidate_id", "")).strip()
    if current_generation_index <= 0 or not current_reference_target_id:
        return {}

    directive_id = str(generation_history.get("directive_id", "")).strip() or str(
        progress_governance.get("directive_id", "")
    ).strip() or str(progress_recommendation.get("directive_id", "")).strip()
    progress_state = str(progress_governance.get("progress_state", "")).strip()
    progress_recommendation_state = str(
        progress_recommendation.get("recommendation_state", "")
    ).strip()
    quality_composite_state = str(
        quality_composite_evaluation.get("composite_quality_state", "")
    ).strip()
    materially_stronger_in_aggregate = bool(
        generation_delta.get(
            "materially_stronger_than_prior_admitted_candidate_in_aggregate",
            quality_composite_evaluation.get(
                "materially_stronger_than_reference_target_in_aggregate", False
            ),
        )
    )
    additional_bounded_improvement_justified = bool(
        progress_governance.get("additional_bounded_improvement_justified", False)
    )
    weak_dimension_ids = _unique_string_list(
        list(progress_governance.get("current_weak_dimension_ids", []))
        or list(quality_composite_evaluation.get("weak_dimension_ids", []))
    )
    newly_improved_dimension_ids = _unique_string_list(
        list(progress_governance.get("newly_improved_dimension_ids", []))
        or list(generation_delta.get("newly_improved_dimension_ids", []))
    )
    persistent_weak_dimension_ids = _unique_string_list(
        list(progress_governance.get("persistent_weak_dimension_ids", []))
        or list(generation_delta.get("persistent_weak_dimension_ids", []))
    )
    regressed_dimension_ids = _unique_string_list(
        list(progress_governance.get("regressed_dimension_ids", []))
        or list(generation_delta.get("regressed_dimension_ids", []))
    )
    history_length = int(progress_governance.get("history_length", 0) or 0)
    weakest_dimension_id = str(
        quality_priority_matrix.get("weakest_dimension_id", "")
    ).strip()
    weakest_dimension_title = str(
        quality_priority_matrix.get("weakest_dimension_title", "")
    ).strip()
    selected_objective_id = str(
        progress_recommendation.get("recommended_objective_id", "")
    ).strip() or str(quality_next_pack_plan.get("selected_objective_id", "")).strip()
    selected_objective_class = str(
        progress_recommendation.get("recommended_objective_class", "")
    ).strip() or str(quality_next_pack_plan.get("selected_objective_class", "")).strip()
    if not selected_objective_class:
        selected_objective_class = _objective_class_from_objective_id(
            selected_objective_id
        )
    selected_skill_pack_id = str(
        progress_recommendation.get("recommended_skill_pack_id", "")
    ).strip() or str(quality_next_pack_plan.get("selected_skill_pack_id", "")).strip()
    selected_dimension_id = str(
        progress_recommendation.get("recommended_dimension_id", "")
    ).strip() or str(quality_next_pack_plan.get("selected_dimension_id", "")).strip()
    selected_dimension_title = str(
        progress_recommendation.get("recommended_dimension_title", "")
    ).strip() or str(quality_next_pack_plan.get("selected_dimension_title", "")).strip()
    if not selected_dimension_title and selected_dimension_id == weakest_dimension_id:
        selected_dimension_title = weakest_dimension_title

    fallback_dimension_definition: dict[str, Any] = {}
    fallback_dimension_id = ""
    for candidate_dimension_id in [
        selected_dimension_id,
        weakest_dimension_id,
        *weak_dimension_ids,
    ]:
        fallback_dimension_definition = _quality_dimension_definition_for_id(
            candidate_dimension_id
        )
        if fallback_dimension_definition and str(
            fallback_dimension_definition.get("objective_class", "")
        ).strip():
            fallback_dimension_id = str(
                fallback_dimension_definition.get("dimension_id", "")
            ).strip() or str(candidate_dimension_id).strip()
            break
    if not selected_dimension_id and fallback_dimension_id:
        selected_dimension_id = fallback_dimension_id
    if not selected_dimension_title:
        selected_dimension_title = str(
            fallback_dimension_definition.get("title", "")
        ).strip() or (
            weakest_dimension_title
            if selected_dimension_id == weakest_dimension_id
            else ""
        )
    if not selected_objective_class:
        selected_objective_class = str(
            fallback_dimension_definition.get("objective_class", "")
        ).strip()
    if not selected_objective_id and selected_objective_class:
        selected_objective_id = selected_objective_class
    if not selected_skill_pack_id:
        selected_skill_pack_id = str(
            fallback_dimension_definition.get("skill_pack_id", "")
        ).strip()

    has_follow_on_candidate = bool(
        selected_objective_id or selected_skill_pack_id or weak_dimension_ids
    )
    broad_multi_dimension_gain = materially_stronger_in_aggregate and (
        quality_composite_state == QUALITY_COMPOSITE_MULTI_DIMENSION_STATE
        or len(newly_improved_dimension_ids) >= 2
    )

    continue_refining_supported = (
        progress_state == GENERATIONAL_IMPROVEMENT_CONFIRMED_STATE
        and additional_bounded_improvement_justified
        and has_follow_on_candidate
        and not broad_multi_dimension_gain
    )
    targeted_remediation_supported = (
        progress_state in {
            GENERATIONAL_IMPROVEMENT_PARTIAL_STATE,
            GENERATIONAL_CHURN_DETECTED_STATE,
        }
        or progress_recommendation_state == PROGRESS_RECOMMENDATION_REMEDIATE_STATE
    ) and has_follow_on_candidate
    next_quality_wave_supported = (
        progress_state == GENERATIONAL_IMPROVEMENT_CONFIRMED_STATE
        and additional_bounded_improvement_justified
        and has_follow_on_candidate
        and broad_multi_dimension_gain
    )
    pause_supported = progress_state in {
        GENERATIONAL_REGRESSION_DETECTED_STATE,
        GENERATIONAL_CHURN_DETECTED_STATE,
    }
    hold_current_supported = progress_recommendation_state == PROGRESS_RECOMMENDATION_HOLD_STATE or (
        progress_state == GENERATIONAL_IMPROVEMENT_CONFIRMED_STATE
        and not additional_bounded_improvement_justified
    )
    hold_and_observe_supported = (
        progress_state == GENERATIONAL_STAGNATION_DETECTED_STATE
        or (
            history_length >= 2
            and not newly_improved_dimension_ids
            and not regressed_dimension_ids
        )
    )

    if progress_state == GENERATIONAL_REGRESSION_DETECTED_STATE:
        selected_strategy_state = STRATEGY_PAUSE_FOR_OPERATOR_REVIEW_STATE
        selected_strategy_rationale = (
            "The current generation is weaker than the prior admitted candidate on one or more important bounded dimensions, so NOVALI should pause for explicit operator review instead of extending the lineage further."
        )
        follow_on_family = STRATEGY_FOLLOW_ON_PENDING_OPERATOR_REVIEW
        operator_review_recommended = True
    elif progress_state == GENERATIONAL_STAGNATION_DETECTED_STATE:
        selected_strategy_state = (
            STRATEGY_HOLD_AND_OBSERVE_BEFORE_FURTHER_CHANGE_STATE
        )
        selected_strategy_rationale = (
            "The lineage currently looks plateaued without meaningful new bounded gain, so the safer posture is to hold and observe before attempting another change wave."
        )
        follow_on_family = STRATEGY_FOLLOW_ON_HOLD_AND_OBSERVE
        operator_review_recommended = True
    elif hold_current_supported:
        selected_strategy_state = STRATEGY_HOLD_CURRENT_REFERENCE_TARGET_STATE
        selected_strategy_rationale = (
            "The current reference target is already materially stronger and no higher-value bounded follow-on is justified right now, so the recommended strategy is to hold the current target rather than keep expanding the wave."
        )
        follow_on_family = STRATEGY_FOLLOW_ON_HOLD_CURRENT_REFERENCE
        operator_review_recommended = False
    elif progress_state == GENERATIONAL_CHURN_DETECTED_STATE:
        selected_strategy_state = STRATEGY_OPEN_TARGETED_REMEDIATION_WAVE_STATE
        selected_strategy_rationale = (
            "This lineage shows movement without stable multi-dimension gain, so the next bounded work should narrow to targeted remediation on the weakest unresolved dimension instead of broad improvement."
        )
        follow_on_family = STRATEGY_FOLLOW_ON_TARGETED_REMEDIATION_WAVE
        operator_review_recommended = True
    elif targeted_remediation_supported:
        selected_strategy_state = STRATEGY_OPEN_TARGETED_REMEDIATION_WAVE_STATE
        selected_strategy_rationale = (
            "The current generation improved only partially, so the most conservative next step is a targeted remediation wave focused on the remaining weak dimensions rather than a broader quality expansion."
        )
        follow_on_family = STRATEGY_FOLLOW_ON_TARGETED_REMEDIATION_WAVE
        operator_review_recommended = False
    elif next_quality_wave_supported:
        selected_strategy_state = STRATEGY_START_NEXT_QUALITY_WAVE_STATE
        selected_strategy_rationale = (
            "The current generation is already materially stronger across multiple bounded dimensions, so NOVALI can shift from narrow refinement into the next bounded quality wave while keeping the current reference target intact."
        )
        follow_on_family = STRATEGY_FOLLOW_ON_NEXT_QUALITY_WAVE
        operator_review_recommended = False
    elif continue_refining_supported:
        selected_strategy_state = (
            STRATEGY_CONTINUE_REFINING_CURRENT_REFERENCE_TARGET_STATE
        )
        selected_strategy_rationale = (
            "Improvement is confirmed but still concentrated enough that the highest-value conservative move is to keep refining the current reference target on the next admissible bounded dimension."
        )
        follow_on_family = STRATEGY_FOLLOW_ON_REFINEMENT_WAVE
        operator_review_recommended = False
    elif progress_recommendation_state in {
        PROGRESS_RECOMMENDATION_PAUSE_STATE,
        PROGRESS_RECOMMENDATION_ESCALATE_STATE,
    }:
        selected_strategy_state = STRATEGY_PAUSE_FOR_OPERATOR_REVIEW_STATE
        selected_strategy_rationale = (
            "The current progress recommendation already advises pausing or escalation, so strategy selection preserves that conservative review posture."
        )
        follow_on_family = STRATEGY_FOLLOW_ON_PENDING_OPERATOR_REVIEW
        operator_review_recommended = True
    else:
        selected_strategy_state = (
            STRATEGY_HOLD_AND_OBSERVE_BEFORE_FURTHER_CHANGE_STATE
        )
        selected_strategy_rationale = (
            "The generational evidence does not yet justify a broader bounded move, so the safer posture is to hold and observe before selecting another improvement wave."
        )
        follow_on_family = STRATEGY_FOLLOW_ON_HOLD_AND_OBSERVE
        operator_review_recommended = True

    strategy_title = _strategy_title(selected_strategy_state)
    follow_on_title = {
        STRATEGY_FOLLOW_ON_REFINEMENT_WAVE: "Successor quality refinement wave",
        STRATEGY_FOLLOW_ON_TARGETED_REMEDIATION_WAVE: "Targeted manifest/test/docs remediation wave",
        STRATEGY_FOLLOW_ON_NEXT_QUALITY_WAVE: "Broader successor quality wave",
        STRATEGY_FOLLOW_ON_PENDING_OPERATOR_REVIEW: "None pending operator review",
        STRATEGY_FOLLOW_ON_HOLD_CURRENT_REFERENCE: "Hold current reference target",
        STRATEGY_FOLLOW_ON_HOLD_AND_OBSERVE: "Hold and observe before further change",
    }.get(follow_on_family, _humanize_objective_id(follow_on_family))
    recommend_execution = selected_strategy_state in {
        STRATEGY_CONTINUE_REFINING_CURRENT_REFERENCE_TARGET_STATE,
        STRATEGY_OPEN_TARGETED_REMEDIATION_WAVE_STATE,
        STRATEGY_START_NEXT_QUALITY_WAVE_STATE,
    }
    recommended_objective_id = selected_objective_id if recommend_execution else ""
    recommended_objective_class = selected_objective_class if recommend_execution else ""
    recommended_skill_pack_id = selected_skill_pack_id if recommend_execution else ""
    recommended_dimension_id = selected_dimension_id if recommend_execution else ""
    recommended_dimension_title = selected_dimension_title if recommend_execution else ""

    strategy_candidate_rows = [
        {
            "strategy_state": STRATEGY_CONTINUE_REFINING_CURRENT_REFERENCE_TARGET_STATE,
            "strategy_title": _strategy_title(
                STRATEGY_CONTINUE_REFINING_CURRENT_REFERENCE_TARGET_STATE
            ),
            "supported": continue_refining_supported,
            "reason": (
                "Supported because progress is confirmed, another bounded gain is justified, and the next safest move is further refinement on the current target."
                if continue_refining_supported
                else "Not selected because the current evidence either does not justify more refinement or already supports holding, remediation, or a broader next wave."
            ),
        },
        {
            "strategy_state": STRATEGY_OPEN_TARGETED_REMEDIATION_WAVE_STATE,
            "strategy_title": _strategy_title(
                STRATEGY_OPEN_TARGETED_REMEDIATION_WAVE_STATE
            ),
            "supported": targeted_remediation_supported,
            "reason": (
                "Supported because unresolved weak dimensions still need targeted bounded remediation before broader expansion."
                if targeted_remediation_supported
                else "Not selected because the current lineage does not primarily call for targeted remediation."
            ),
        },
        {
            "strategy_state": STRATEGY_START_NEXT_QUALITY_WAVE_STATE,
            "strategy_title": _strategy_title(
                STRATEGY_START_NEXT_QUALITY_WAVE_STATE
            ),
            "supported": next_quality_wave_supported,
            "reason": (
                "Supported because multiple bounded dimensions are already stronger, making a broader next quality wave conservative and justified."
                if next_quality_wave_supported
                else "Not selected because the current lineage is not yet strong enough across dimensions to justify opening the next quality wave."
            ),
        },
        {
            "strategy_state": STRATEGY_PAUSE_FOR_OPERATOR_REVIEW_STATE,
            "strategy_title": _strategy_title(
                STRATEGY_PAUSE_FOR_OPERATOR_REVIEW_STATE
            ),
            "supported": pause_supported,
            "reason": (
                "Supported because the current lineage shows regression or unstable churn that should be reviewed explicitly before more change."
                if pause_supported
                else "Not selected because the current lineage does not currently require a pause-first posture."
            ),
        },
        {
            "strategy_state": STRATEGY_HOLD_CURRENT_REFERENCE_TARGET_STATE,
            "strategy_title": _strategy_title(
                STRATEGY_HOLD_CURRENT_REFERENCE_TARGET_STATE
            ),
            "supported": hold_current_supported,
            "reason": (
                "Supported because the current reference target is strong enough that no higher-value bounded follow-on is justified immediately."
                if hold_current_supported
                else "Not selected because the lineage still needs either more bounded work or more explicit observation."
            ),
        },
        {
            "strategy_state": STRATEGY_HOLD_AND_OBSERVE_BEFORE_FURTHER_CHANGE_STATE,
            "strategy_title": _strategy_title(
                STRATEGY_HOLD_AND_OBSERVE_BEFORE_FURTHER_CHANGE_STATE
            ),
            "supported": hold_and_observe_supported,
            "reason": (
                "Supported because the lineage currently looks plateaued enough to warrant observation before another change wave."
                if hold_and_observe_supported
                else "Not selected because the lineage already points to a clearer continue/remediate/hold decision."
            ),
        },
    ]
    rejected_alternatives = [
        {
            "strategy_state": str(item.get("strategy_state", "")).strip(),
            "strategy_title": str(item.get("strategy_title", "")).strip(),
            "rejected_reason": str(item.get("reason", "")).strip(),
        }
        for item in strategy_candidate_rows
        if str(item.get("strategy_state", "")).strip() != selected_strategy_state
    ]

    selection_payload = {
        "schema_name": SUCCESSOR_STRATEGY_SELECTION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_STRATEGY_SELECTION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_generation_index": current_generation_index,
        "current_reference_target_id": current_reference_target_id,
        "current_admitted_candidate_id": str(
            generation_delta.get("current_admitted_candidate_id", "")
        ).strip(),
        "prior_admitted_candidate_id": str(
            generation_delta.get("prior_admitted_candidate_id", "")
        ).strip(),
        "progress_state": progress_state,
        "progress_recommendation_state": progress_recommendation_state,
        "selected_strategy_state": selected_strategy_state,
        "selected_strategy_title": strategy_title,
        "selected_strategy_rationale": selected_strategy_rationale,
        "selected_follow_on_family": follow_on_family,
        "operator_review_recommended": operator_review_recommended,
        "reference_target_consumption_state": str(
            reference_target_consumption.get("consumption_state", "")
        ).strip(),
        "protected_live_baseline_reference_id": str(
            reference_target_consumption.get(
                "protected_live_baseline_reference_id",
                reference_target.get("protected_live_baseline_reference_id", ""),
            )
        ).strip(),
        "materially_stronger_than_prior_admitted_candidate_in_aggregate": materially_stronger_in_aggregate,
        "additional_bounded_improvement_justified": additional_bounded_improvement_justified,
        "weak_dimension_ids": weak_dimension_ids,
        "selected_follow_on_objective_id": recommended_objective_id,
        "selected_follow_on_objective_class": recommended_objective_class,
        "selected_follow_on_skill_pack_id": recommended_skill_pack_id,
        "selected_follow_on_dimension_id": recommended_dimension_id,
        "selected_follow_on_dimension_title": recommended_dimension_title,
        "rejected_alternative_strategy_count": len(rejected_alternatives),
        "baseline_mutation_performed": False,
    }
    rationale_payload = {
        "schema_name": SUCCESSOR_STRATEGY_RATIONALE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_STRATEGY_RATIONALE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_generation_index": current_generation_index,
        "current_reference_target_id": current_reference_target_id,
        "selected_strategy_state": selected_strategy_state,
        "selected_strategy_title": strategy_title,
        "selected_strategy_rationale": selected_strategy_rationale,
        "key_evidence": {
            "progress_state": progress_state,
            "progress_recommendation_state": progress_recommendation_state,
            "quality_composite_state": quality_composite_state,
            "materially_stronger_than_prior_admitted_candidate_in_aggregate": materially_stronger_in_aggregate,
            "additional_bounded_improvement_justified": additional_bounded_improvement_justified,
            "newly_improved_dimension_ids": newly_improved_dimension_ids,
            "persistent_weak_dimension_ids": persistent_weak_dimension_ids,
            "regressed_dimension_ids": regressed_dimension_ids,
            "weak_dimension_ids": weak_dimension_ids,
            "weakest_dimension_id": weakest_dimension_id,
            "weakest_dimension_title": weakest_dimension_title,
        },
        "rejected_alternative_strategies": rejected_alternatives,
    }
    follow_on_plan_payload = {
        "schema_name": SUCCESSOR_STRATEGY_FOLLOW_ON_PLAN_SCHEMA_NAME,
        "schema_version": SUCCESSOR_STRATEGY_FOLLOW_ON_PLAN_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_generation_index": current_generation_index,
        "current_reference_target_id": current_reference_target_id,
        "selected_strategy_state": selected_strategy_state,
        "selected_strategy_title": strategy_title,
        "follow_on_family": follow_on_family,
        "follow_on_family_title": follow_on_title,
        "recommended_objective_id": recommended_objective_id,
        "recommended_objective_class": recommended_objective_class,
        "recommended_skill_pack_id": recommended_skill_pack_id,
        "recommended_dimension_id": recommended_dimension_id,
        "recommended_dimension_title": recommended_dimension_title,
        "operator_review_recommended_before_execution": operator_review_recommended,
        "execution_readiness_state": (
            "ready_for_bounded_follow_on"
            if recommend_execution and not operator_review_recommended
            else (
                "pending_operator_review"
                if operator_review_recommended
                else "hold_without_immediate_follow_on"
            )
        ),
        "bounded_execution_scope": "active_workspace_only",
        "rationale": selected_strategy_rationale,
        "baseline_mutation_performed": False,
    }
    decision_support_payload = {
        "schema_name": SUCCESSOR_STRATEGY_DECISION_SUPPORT_SCHEMA_NAME,
        "schema_version": SUCCESSOR_STRATEGY_DECISION_SUPPORT_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_generation_index": current_generation_index,
        "current_reference_target_id": current_reference_target_id,
        "progress_state": progress_state,
        "progress_recommendation_state": progress_recommendation_state,
        "quality_composite_state": quality_composite_state,
        "materially_stronger_than_prior_admitted_candidate_in_aggregate": materially_stronger_in_aggregate,
        "additional_bounded_improvement_justified": additional_bounded_improvement_justified,
        "selected_strategy_state": selected_strategy_state,
        "selected_follow_on_family": follow_on_family,
        "candidate_strategy_rows": strategy_candidate_rows,
        "evidence_used": {
            "generation_history_path": str(paths["generation_history_path"]),
            "generation_delta_path": str(paths["generation_delta_path"]),
            "progress_governance_path": str(paths["progress_governance_path"]),
            "progress_recommendation_path": str(paths["progress_recommendation_path"]),
            "quality_roadmap_path": str(paths["quality_roadmap_path"]),
            "quality_priority_matrix_path": str(paths["quality_priority_matrix_path"]),
            "quality_composite_evaluation_path": str(
                paths["quality_composite_evaluation_path"]
            ),
            "quality_next_pack_plan_path": str(paths["quality_next_pack_plan_path"]),
            "reference_target_path": str(paths["reference_target_path"]),
            "reference_target_consumption_path": str(
                paths["reference_target_consumption_path"]
            ),
        },
    }
    return {
        "strategy_selection": selection_payload,
        "strategy_rationale": rationale_payload,
        "strategy_follow_on_plan": follow_on_plan_payload,
        "strategy_decision_support": decision_support_payload,
    }


def _materialize_successor_strategy_selection_outputs(
    *,
    workspace_root: Path,
    runtime_event_log_path: Path | None = None,
    session_id: str = "",
    directive_id: str = "",
    execution_profile: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    outputs = _evaluate_successor_strategy_selection_state(workspace_root=workspace_root)
    if not outputs:
        return {
            "strategy_selection": load_json(paths["strategy_selection_path"]),
            "strategy_rationale": load_json(paths["strategy_rationale_path"]),
            "strategy_follow_on_plan": load_json(paths["strategy_follow_on_plan_path"]),
            "strategy_decision_support": load_json(
                paths["strategy_decision_support_path"]
            ),
            "strategy_selection_path": str(paths["strategy_selection_path"]),
            "strategy_rationale_path": str(paths["strategy_rationale_path"]),
            "strategy_follow_on_plan_path": str(paths["strategy_follow_on_plan_path"]),
            "strategy_decision_support_path": str(
                paths["strategy_decision_support_path"]
            ),
        }

    write_rows = [
        (
            paths["strategy_selection_path"],
            dict(outputs.get("strategy_selection", {})),
            "successor_strategy_selection_json",
        ),
        (
            paths["strategy_rationale_path"],
            dict(outputs.get("strategy_rationale", {})),
            "successor_strategy_rationale_json",
        ),
        (
            paths["strategy_follow_on_plan_path"],
            dict(outputs.get("strategy_follow_on_plan", {})),
            "successor_strategy_follow_on_plan_json",
        ),
        (
            paths["strategy_decision_support_path"],
            dict(outputs.get("strategy_decision_support", {})),
            "successor_strategy_decision_support_json",
        ),
    ]
    if runtime_event_log_path and str(runtime_event_log_path) not in {"", "."}:
        for artifact_path, artifact_payload, artifact_kind in write_rows:
            _write_json(
                artifact_path,
                artifact_payload,
                log_path=runtime_event_log_path,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=workspace_id,
                workspace_root=str(workspace_root),
                work_item_id="successor_strategy_selection",
                artifact_kind=artifact_kind,
            )
        _event(
            runtime_event_log_path,
            event_type="successor_strategy_selection_recorded",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            generation_index=int(
                dict(outputs.get("strategy_selection", {})).get(
                    "current_generation_index", 0
                )
                or 0
            ),
            progress_state=str(
                dict(outputs.get("strategy_selection", {})).get("progress_state", "")
            ),
            progress_recommendation_state=str(
                dict(outputs.get("strategy_selection", {})).get(
                    "progress_recommendation_state", ""
                )
            ),
            strategy_state=str(
                dict(outputs.get("strategy_selection", {})).get(
                    "selected_strategy_state", ""
                )
            ),
            follow_on_family=str(
                dict(outputs.get("strategy_follow_on_plan", {})).get(
                    "follow_on_family", ""
                )
            ),
            follow_on_objective_id=str(
                dict(outputs.get("strategy_follow_on_plan", {})).get(
                    "recommended_objective_id", ""
                )
            ),
            operator_review_recommended=bool(
                dict(outputs.get("strategy_follow_on_plan", {})).get(
                    "operator_review_recommended_before_execution", False
                )
            ),
            strategy_selection_path=str(paths["strategy_selection_path"]),
            strategy_follow_on_plan_path=str(paths["strategy_follow_on_plan_path"]),
        )
    else:
        for artifact_path, artifact_payload, _artifact_kind in write_rows:
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    _sync_strategy_selection_to_latest_artifacts(
        workspace_root=workspace_root,
        paths=paths,
        strategy_selection=dict(outputs.get("strategy_selection", {})),
        strategy_rationale=dict(outputs.get("strategy_rationale", {})),
        strategy_follow_on_plan=dict(outputs.get("strategy_follow_on_plan", {})),
        strategy_decision_support=dict(outputs.get("strategy_decision_support", {})),
    )
    return {
        **outputs,
        "strategy_selection_path": str(paths["strategy_selection_path"]),
        "strategy_rationale_path": str(paths["strategy_rationale_path"]),
        "strategy_follow_on_plan_path": str(paths["strategy_follow_on_plan_path"]),
        "strategy_decision_support_path": str(
            paths["strategy_decision_support_path"]
        ),
    }


def _campaign_state_title(campaign_state: str) -> str:
    normalized = str(campaign_state or "").strip()
    return {
        CAMPAIGN_CONTINUE_CURRENT_WAVE_FAMILY_STATE: "Continue current campaign wave family",
        CAMPAIGN_SHIFT_TO_TARGETED_REMEDIATION_STATE: "Shift to targeted remediation",
        CAMPAIGN_START_NEXT_QUALITY_WAVE_STATE: "Start next quality wave",
        CAMPAIGN_REFRESH_REVISED_CANDIDATE_STATE: "Refresh revised candidate",
        CAMPAIGN_PAUSE_FOR_OPERATOR_REVIEW_STATE: "Pause for operator review",
        CAMPAIGN_HOLD_CURRENT_REFERENCE_TARGET_STATE: "Hold current reference target",
        CAMPAIGN_CONVERGENCE_DETECTED_STATE: "Campaign convergence detected",
    }.get(
        normalized,
        _humanize_objective_id(normalized) or "Unspecified campaign state",
    )


def _campaign_recommendation_title(recommendation_state: str) -> str:
    normalized = str(recommendation_state or "").strip()
    return {
        CAMPAIGN_RECOMMENDATION_CONTINUE_STATE: "Continue current campaign",
        CAMPAIGN_RECOMMENDATION_REMEDIATE_STATE: "Shift to targeted remediation wave",
        CAMPAIGN_RECOMMENDATION_NEXT_QUALITY_WAVE_STATE: "Start next quality wave",
        CAMPAIGN_RECOMMENDATION_REFRESH_STATE: "Refresh revised candidate now",
        CAMPAIGN_RECOMMENDATION_PAUSE_STATE: "Pause for operator review",
        CAMPAIGN_RECOMMENDATION_HOLD_STATE: "Hold current reference target pending more evidence",
    }.get(
        normalized,
        _humanize_objective_id(normalized)
        or "Unspecified campaign recommendation",
    )


def _campaign_follow_on_title(follow_on_family: str) -> str:
    normalized = str(follow_on_family or "").strip()
    return {
        CAMPAIGN_FOLLOW_ON_CURRENT_WAVE_CONTINUATION: "Current wave family continuation",
        STRATEGY_FOLLOW_ON_TARGETED_REMEDIATION_WAVE: "Targeted quality remediation wave",
        STRATEGY_FOLLOW_ON_NEXT_QUALITY_WAVE: "Broader successor quality wave",
        CAMPAIGN_FOLLOW_ON_REVISED_CANDIDATE_REFRESH: "Revised candidate refresh wave",
        STRATEGY_FOLLOW_ON_PENDING_OPERATOR_REVIEW: "None pending operator review",
        STRATEGY_FOLLOW_ON_HOLD_CURRENT_REFERENCE: "Hold current reference target",
        STRATEGY_FOLLOW_ON_HOLD_AND_OBSERVE: "Hold and observe before further change",
    }.get(normalized, _humanize_objective_id(normalized) or "Unspecified follow-on")


def _campaign_cycle_state_title(campaign_cycle_state: str) -> str:
    normalized = str(campaign_cycle_state or "").strip()
    return {
        CAMPAIGN_CYCLE_START_NEXT_CAMPAIGN_STATE: "Start next campaign cycle",
        CAMPAIGN_CYCLE_HOLD_NEW_REFERENCE_TARGET_STATE: "Hold new reference target",
        CAMPAIGN_CYCLE_TARGETED_POST_ROLLOVER_REMEDIATION_STATE: "Open targeted post-rollover remediation",
        CAMPAIGN_CYCLE_PAUSE_FOR_OPERATOR_REVIEW_STATE: "Pause for operator review",
        CAMPAIGN_CYCLE_DIMINISHING_RETURNS_DETECTED_STATE: "Campaign-cycle diminishing returns detected",
        CAMPAIGN_CYCLE_CONVERGENCE_CONFIRMED_STATE: "Campaign-cycle convergence confirmed",
        CAMPAIGN_CYCLE_REGRESSION_DETECTED_STATE: "Campaign-cycle regression detected",
    }.get(
        normalized,
        _humanize_objective_id(normalized) or "Unspecified campaign-cycle state",
    )


def _campaign_cycle_recommendation_title(recommendation_state: str) -> str:
    normalized = str(recommendation_state or "").strip()
    return {
        CAMPAIGN_CYCLE_RECOMMENDATION_START_STATE: "Start next campaign cycle",
        CAMPAIGN_CYCLE_RECOMMENDATION_HOLD_STATE: "Hold new reference target",
        CAMPAIGN_CYCLE_RECOMMENDATION_REMEDIATE_STATE: "Open targeted post-rollover remediation",
        CAMPAIGN_CYCLE_RECOMMENDATION_PAUSE_STATE: "Pause for operator review",
        CAMPAIGN_CYCLE_RECOMMENDATION_OBSERVE_STATE: "Continue observing before new cycle",
    }.get(
        normalized,
        _humanize_objective_id(normalized)
        or "Unspecified campaign-cycle recommendation",
    )


def _campaign_cycle_follow_on_title(follow_on_family: str) -> str:
    normalized = str(follow_on_family or "").strip()
    return {
        CAMPAIGN_CYCLE_FOLLOW_ON_NEXT_CAMPAIGN: "Successor quality campaign wave",
        CAMPAIGN_CYCLE_FOLLOW_ON_HOLD_NEW_REFERENCE: "Hold new reference target",
        CAMPAIGN_CYCLE_FOLLOW_ON_TARGETED_POST_ROLLOVER_REMEDIATION: "Targeted post-rollover remediation wave",
        STRATEGY_FOLLOW_ON_PENDING_OPERATOR_REVIEW: "None pending operator review",
        CAMPAIGN_CYCLE_FOLLOW_ON_OBSERVE: "Observe current reference target before a new cycle",
    }.get(
        normalized,
        _humanize_objective_id(normalized) or "Unspecified campaign-cycle follow-on",
    )


def _loop_state_title(loop_state: str) -> str:
    normalized = str(loop_state or "").strip()
    return {
        LOOP_START_NEXT_FULL_CAMPAIGN_STATE: "Start next full loop",
        LOOP_HOLD_CURRENT_REFERENCE_TARGET_STATE: "Hold current reference target",
        LOOP_ALLOW_ONLY_TARGETED_REMEDIATION_STATE: "Allow only targeted remediation",
        LOOP_PAUSE_FOR_OPERATOR_REVIEW_STATE: "Pause for operator review",
        LOOP_DIMINISHING_RETURNS_DETECTED_STATE: "Loop-level diminishing returns detected",
        LOOP_CONVERGENCE_CONFIRMED_STATE: "Loop-level convergence confirmed",
        LOOP_REGRESSION_DETECTED_STATE: "Loop-level regression detected",
    }.get(normalized, _humanize_objective_id(normalized) or "Unspecified loop state")


def _loop_recommendation_title(recommendation_state: str) -> str:
    normalized = str(recommendation_state or "").strip()
    return {
        LOOP_RECOMMENDATION_START_STATE: "Start next full loop",
        LOOP_RECOMMENDATION_HOLD_STATE: "Hold current bounded target",
        LOOP_RECOMMENDATION_REMEDIATE_STATE: "Allow only targeted remediation",
        LOOP_RECOMMENDATION_PAUSE_STATE: "Pause for operator review",
        LOOP_RECOMMENDATION_OBSERVE_STATE: "Continue observing before new loop",
    }.get(
        normalized,
        _humanize_objective_id(normalized) or "Unspecified loop recommendation",
    )


def _loop_follow_on_title(follow_on_family: str) -> str:
    normalized = str(follow_on_family or "").strip()
    return {
        LOOP_FOLLOW_ON_NEXT_FULL_CAMPAIGN: "Successor quality campaign wave",
        LOOP_FOLLOW_ON_HOLD_CURRENT_REFERENCE: "Hold current reference target",
        LOOP_FOLLOW_ON_TARGETED_REMEDIATION: "Targeted post-rollover remediation wave",
        LOOP_FOLLOW_ON_PENDING_OPERATOR_REVIEW: "None pending operator review",
        LOOP_FOLLOW_ON_OBSERVE: "Observe current reference target before a new loop",
    }.get(normalized, _humanize_objective_id(normalized) or "Unspecified loop follow-on")


def _infer_campaign_wave_context(
    *,
    current_objective: dict[str, Any],
    quality_dimension_id: str,
    strategy_selection: dict[str, Any],
    strategy_follow_on_plan: dict[str, Any],
    campaign_recommendation: dict[str, Any],
    campaign_wave_plan: dict[str, Any],
    campaign_cycle_recommendation: dict[str, Any],
    campaign_cycle_follow_on_plan: dict[str, Any],
) -> dict[str, str]:
    objective_id = str(current_objective.get("objective_id", "")).strip()
    objective_class = str(current_objective.get("objective_class", "")).strip() or (
        _objective_class_from_objective_id(objective_id)
    )
    cycle_plan_objective_id = str(
        campaign_cycle_follow_on_plan.get("recommended_objective_id", "")
    ).strip()
    cycle_plan_objective_class = str(
        campaign_cycle_follow_on_plan.get("recommended_objective_class", "")
    ).strip()
    if objective_id and (
        objective_id == cycle_plan_objective_id
        or (objective_class and objective_class == cycle_plan_objective_class)
    ):
        return {
            "strategy_state": str(
                campaign_cycle_recommendation.get("recommendation_state", "")
            ).strip()
            or str(campaign_cycle_follow_on_plan.get("campaign_cycle_state", "")).strip(),
            "follow_on_family": str(
                campaign_cycle_follow_on_plan.get("recommended_follow_on_family", "")
            ).strip(),
            "wave_context_source": "current_campaign_cycle_follow_on_plan",
        }

    campaign_plan_objective_id = str(
        campaign_wave_plan.get("recommended_objective_id", "")
    ).strip()
    campaign_plan_objective_class = str(
        campaign_wave_plan.get("recommended_objective_class", "")
    ).strip()
    if objective_id and (
        objective_id == campaign_plan_objective_id
        or (objective_class and objective_class == campaign_plan_objective_class)
    ):
        return {
            "strategy_state": str(
                campaign_recommendation.get("recommendation_state", "")
            ).strip()
            or str(campaign_wave_plan.get("campaign_state", "")).strip(),
            "follow_on_family": str(
                campaign_wave_plan.get("recommended_follow_on_family", "")
            ).strip(),
            "wave_context_source": "current_campaign_follow_on_plan",
        }

    plan_objective_id = str(
        strategy_follow_on_plan.get("recommended_objective_id", "")
    ).strip()
    plan_objective_class = str(
        strategy_follow_on_plan.get("recommended_objective_class", "")
    ).strip()
    if objective_id and (
        objective_id == plan_objective_id
        or (objective_class and objective_class == plan_objective_class)
    ):
        return {
            "strategy_state": str(
                strategy_selection.get("selected_strategy_state", "")
            ).strip(),
            "follow_on_family": str(
                strategy_follow_on_plan.get("follow_on_family", "")
            ).strip(),
            "wave_context_source": "current_strategy_follow_on_plan",
        }

    dimension_definition = _quality_dimension_definition_for_id(quality_dimension_id)
    if objective_class.startswith("refine_"):
        return {
            "strategy_state": STRATEGY_OPEN_TARGETED_REMEDIATION_WAVE_STATE,
            "follow_on_family": STRATEGY_FOLLOW_ON_TARGETED_REMEDIATION_WAVE,
            "wave_context_source": "objective_family_inference",
        }
    if objective_class in {
        "improve_successor_package_readiness",
        "strengthen_successor_test_coverage",
        "refine_successor_artifact_index_consistency",
        "improve_successor_handoff_completeness",
        "review_and_expand_workspace_local_implementation",
    } or str(dimension_definition.get("priority_level", "")).strip() in {
        "high",
        "medium",
    }:
        return {
            "strategy_state": STRATEGY_START_NEXT_QUALITY_WAVE_STATE,
            "follow_on_family": STRATEGY_FOLLOW_ON_NEXT_QUALITY_WAVE,
            "wave_context_source": "objective_family_inference",
        }
    return {
        "strategy_state": str(
            strategy_selection.get("selected_strategy_state", "")
        ).strip(),
        "follow_on_family": str(
            strategy_follow_on_plan.get("follow_on_family", "")
        ).strip(),
        "wave_context_source": "post_wave_strategy_fallback",
    }


def _evaluate_successor_campaign_governance_state(
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    generation_history = load_json(paths["generation_history_path"])
    generation_delta = load_json(paths["generation_delta_path"])
    progress_governance = load_json(paths["progress_governance_path"])
    progress_recommendation = load_json(paths["progress_recommendation_path"])
    strategy_selection = load_json(paths["strategy_selection_path"])
    strategy_follow_on_plan = load_json(paths["strategy_follow_on_plan_path"])
    campaign_recommendation = load_json(paths["campaign_recommendation_path"])
    campaign_wave_plan = load_json(paths["campaign_wave_plan_path"])
    campaign_cycle_recommendation = load_json(
        paths["campaign_cycle_recommendation_path"]
    )
    campaign_cycle_follow_on_plan = load_json(
        paths["campaign_cycle_follow_on_plan_path"]
    )
    quality_composite_evaluation = load_json(paths["quality_composite_evaluation_path"])
    quality_next_pack_plan = load_json(paths["quality_next_pack_plan_path"])
    reference_target = load_json(paths["reference_target_path"])
    reference_target_consumption = load_json(paths["reference_target_consumption_path"])
    skill_pack_invocation = load_json(paths["skill_pack_invocation_path"])
    skill_pack_result = load_json(paths["skill_pack_result_path"])
    quality_gap_summary = load_json(paths["quality_gap_summary_path"])
    quality_improvement_summary = load_json(paths["quality_improvement_summary_path"])
    prior_campaign_history = load_json(paths["campaign_history_path"])

    current_generation_index = int(
        generation_history.get("current_generation_index", 0)
        or strategy_selection.get("current_generation_index", 0)
        or 0
    )
    current_reference_target_id = str(
        reference_target.get("preferred_reference_target_id", "")
    ).strip() or str(
        reference_target_consumption.get("active_bounded_reference_target_id", "")
    ).strip() or str(
        generation_history.get("current_admitted_candidate_id", "")
    ).strip()
    if current_generation_index <= 0 or not current_reference_target_id:
        return {}

    directive_id = str(generation_history.get("directive_id", "")).strip() or str(
        progress_governance.get("directive_id", "")
    ).strip() or str(strategy_selection.get("directive_id", "")).strip()
    progress_state = str(progress_governance.get("progress_state", "")).strip()
    progress_recommendation_state = str(
        progress_recommendation.get("recommendation_state", "")
    ).strip()
    strategy_state = str(
        strategy_selection.get("selected_strategy_state", "")
    ).strip()
    materially_stronger_in_aggregate = bool(
        generation_delta.get(
            "materially_stronger_than_prior_admitted_candidate_in_aggregate",
            quality_composite_evaluation.get(
                "materially_stronger_than_reference_target_in_aggregate",
                False,
            ),
        )
    )
    weak_dimension_ids = _unique_string_list(
        list(progress_governance.get("current_weak_dimension_ids", []))
        or list(quality_composite_evaluation.get("weak_dimension_ids", []))
    )
    regressed_dimension_ids = _unique_string_list(
        list(progress_governance.get("regressed_dimension_ids", []))
        or list(generation_delta.get("regressed_dimension_ids", []))
    )
    newly_improved_dimension_ids = _unique_string_list(
        list(progress_governance.get("newly_improved_dimension_ids", []))
        or list(generation_delta.get("newly_improved_dimension_ids", []))
        or list(quality_composite_evaluation.get("improved_dimension_ids", []))
    )
    current_objective = dict(skill_pack_invocation.get("current_objective", {}))
    quality_dimension_id = str(
        quality_improvement_summary.get("quality_dimension_id", "")
    ).strip() or str(skill_pack_result.get("quality_dimension_id", "")).strip() or str(
        skill_pack_invocation.get("quality_dimension_id", "")
    ).strip()
    quality_dimension_title = str(
        quality_improvement_summary.get("quality_dimension_title", "")
    ).strip() or str(skill_pack_result.get("quality_dimension_title", "")).strip() or str(
        skill_pack_invocation.get("quality_dimension_title", "")
    ).strip()
    wave_context = _infer_campaign_wave_context(
        current_objective=current_objective,
        quality_dimension_id=quality_dimension_id,
        strategy_selection=strategy_selection,
        strategy_follow_on_plan=strategy_follow_on_plan,
        campaign_recommendation=campaign_recommendation,
        campaign_wave_plan=campaign_wave_plan,
        campaign_cycle_recommendation=campaign_cycle_recommendation,
        campaign_cycle_follow_on_plan=campaign_cycle_follow_on_plan,
    )

    campaign_id = f"campaign::{current_reference_target_id}"
    prior_campaigns = [
        dict(item)
        for item in list(prior_campaign_history.get("campaigns", []))
        if isinstance(item, dict)
    ]
    current_campaign: dict[str, Any] | None = None
    preserved_campaigns: list[dict[str, Any]] = []
    for item in prior_campaigns:
        if str(item.get("campaign_id", "")).strip() == campaign_id:
            current_campaign = dict(item)
        else:
            preserved_campaigns.append(dict(item))
    if current_campaign is None:
        current_campaign = {
            "campaign_id": campaign_id,
            "reference_target_id": current_reference_target_id,
            "start_generation_index": int(current_generation_index),
            "start_generated_at": _now(),
            "waves": [],
        }

    current_campaign["directive_id"] = directive_id
    current_campaign["workspace_id"] = str(workspace_root.name)
    current_campaign["workspace_root"] = str(workspace_root)
    current_campaign["reference_target_id"] = current_reference_target_id
    current_campaign["current_generation_index"] = int(current_generation_index)
    current_campaign["protected_live_baseline_reference_id"] = str(
        reference_target_consumption.get(
            "protected_live_baseline_reference_id",
            reference_target.get("protected_live_baseline_reference_id", ""),
        )
    ).strip()
    current_campaign["reference_target_consumption_state"] = str(
        reference_target_consumption.get("consumption_state", "")
    ).strip()
    current_campaign["reference_target_rollover_state"] = str(
        reference_target.get("reference_target_rollover_state", "")
    ).strip()

    waves = [
        dict(item)
        for item in list(current_campaign.get("waves", []))
        if isinstance(item, dict)
    ]
    latest_wave_generated_at = str(
        skill_pack_result.get("generated_at", "")
    ).strip() or str(quality_improvement_summary.get("generated_at", "")).strip() or str(
        skill_pack_invocation.get("generated_at", "")
    ).strip()
    latest_skill_pack_id = str(
        skill_pack_result.get("selected_skill_pack_id", "")
    ).strip() or str(skill_pack_invocation.get("selected_skill_pack_id", "")).strip()
    current_objective_id = str(current_objective.get("objective_id", "")).strip() or str(
        strategy_follow_on_plan.get("recommended_objective_id", "")
    ).strip() or str(progress_recommendation.get("recommended_objective_id", "")).strip()
    current_objective_class = str(
        current_objective.get("objective_class", "")
    ).strip() or str(
        strategy_follow_on_plan.get("recommended_objective_class", "")
    ).strip() or str(
        progress_recommendation.get("recommended_objective_class", "")
    ).strip()
    if not current_objective_class:
        current_objective_class = _objective_class_from_objective_id(
            current_objective_id
        )
    latest_wave_fingerprint = "|".join(
        [
            campaign_id,
            latest_wave_generated_at,
            latest_skill_pack_id,
            current_objective_id,
            quality_dimension_id,
            str(skill_pack_result.get("cycle_index", "")).strip()
            or str(skill_pack_invocation.get("cycle_index", "")).strip(),
        ]
    ).strip("|")
    existing_wave_fingerprints = {
        str(item.get("wave_fingerprint", "")).strip()
        for item in waves
        if str(item.get("wave_fingerprint", "")).strip()
    }
    if latest_wave_generated_at and latest_skill_pack_id and (
        latest_wave_fingerprint not in existing_wave_fingerprints
    ):
        waves.append(
            {
                "wave_index": len(waves) + 1,
                "wave_fingerprint": latest_wave_fingerprint,
                "recorded_at": _now(),
                "wave_generated_at": latest_wave_generated_at,
                "generation_index": int(current_generation_index),
                "strategy_state": str(wave_context.get("strategy_state", "")).strip(),
                "follow_on_family": str(
                    wave_context.get("follow_on_family", "")
                ).strip(),
                "wave_context_source": str(
                    wave_context.get("wave_context_source", "")
                ).strip(),
                "objective_id": current_objective_id,
                "objective_class": current_objective_class,
                "selected_skill_pack_id": latest_skill_pack_id,
                "selected_skill_pack_title": str(
                    skill_pack_result.get("selected_skill_pack_title", "")
                ).strip()
                or str(skill_pack_invocation.get("selected_skill_pack_title", "")).strip(),
                "quality_gap_id": str(
                    quality_gap_summary.get("quality_gap_id", "")
                ).strip(),
                "quality_dimension_id": quality_dimension_id,
                "quality_dimension_title": quality_dimension_title,
                "quality_composite_state": str(
                    quality_improvement_summary.get("quality_composite_state", "")
                ).strip()
                or str(skill_pack_result.get("quality_composite_state", "")).strip(),
                "result_state": str(skill_pack_result.get("result_state", "")).strip(),
                "improvement_state": str(
                    quality_improvement_summary.get("improvement_state", "")
                ).strip(),
                "improved_relative_to_reference_target": bool(
                    quality_improvement_summary.get(
                        "improved_relative_to_reference_target",
                        False,
                    )
                ),
                "materially_stronger_than_reference_target_in_aggregate": bool(
                    quality_improvement_summary.get(
                        "materially_stronger_than_reference_target_in_aggregate",
                        False,
                    )
                ),
                "progress_state": progress_state,
                "progress_recommendation_state": progress_recommendation_state,
                "operator_review_recommended": bool(
                    strategy_follow_on_plan.get(
                        "operator_review_recommended_before_execution",
                        strategy_selection.get("operator_review_recommended", False),
                    )
                ),
                "files_created_or_modified": list(
                    quality_improvement_summary.get("files_created_or_modified", [])
                ),
            }
        )

    successful_waves = [
        item
        for item in waves
        if str(item.get("result_state", "")).strip() == "complete"
        and bool(item.get("improved_relative_to_reference_target", False))
    ]
    accumulated_improved_dimension_ids = _unique_string_list(
        [
            item.get("quality_dimension_id", "")
            for item in successful_waves
            if str(item.get("quality_dimension_id", "")).strip()
        ]
    )
    accumulated_partial_dimension_ids = _unique_string_list(
        [
            item.get("quality_dimension_id", "")
            for item in waves
            if str(item.get("improvement_state", "")).strip() == "partial"
        ]
    )
    last_wave = dict(waves[-1]) if waves else {}
    prior_accumulated_improved_dimension_ids = _unique_string_list(
        [
            item.get("quality_dimension_id", "")
            for item in successful_waves[:-1]
            if str(item.get("quality_dimension_id", "")).strip()
        ]
    )
    last_wave_dimension_id = str(last_wave.get("quality_dimension_id", "")).strip()
    latest_wave_added_new_dimension = bool(
        last_wave_dimension_id
        and last_wave_dimension_id not in prior_accumulated_improved_dimension_ids
        and bool(last_wave.get("improved_relative_to_reference_target", False))
    )

    refresh_revised_candidate_justified = bool(
        len(waves) >= 2
        and len(accumulated_improved_dimension_ids) >= 2
        and materially_stronger_in_aggregate
        and not regressed_dimension_ids
        and progress_recommendation_state == PROGRESS_RECOMMENDATION_HOLD_STATE
    )
    campaign_convergence_detected = bool(
        refresh_revised_candidate_justified or (
            len(waves) >= 2
            and materially_stronger_in_aggregate
            and not regressed_dimension_ids
            and not weak_dimension_ids
        )
    )
    campaign_diminishing_returns_detected = bool(
        len(waves) >= 2
        and materially_stronger_in_aggregate
        and not regressed_dimension_ids
        and not latest_wave_added_new_dimension
    )

    if regressed_dimension_ids or progress_state == GENERATIONAL_REGRESSION_DETECTED_STATE:
        campaign_progress_state = CAMPAIGN_REGRESSION_STATE
        campaign_state = CAMPAIGN_PAUSE_FOR_OPERATOR_REVIEW_STATE
        recommendation_state = CAMPAIGN_RECOMMENDATION_PAUSE_STATE
        recommendation_rationale = (
            "Campaign evidence now records regression against the current admitted reference target lineage, so the conservative posture is to pause for explicit operator review."
        )
        recommended_follow_on_family = STRATEGY_FOLLOW_ON_PENDING_OPERATOR_REVIEW
        operator_review_recommended = True
    elif refresh_revised_candidate_justified:
        campaign_progress_state = CAMPAIGN_CONVERGENCE_STATE
        campaign_state = CAMPAIGN_REFRESH_REVISED_CANDIDATE_STATE
        recommendation_state = CAMPAIGN_RECOMMENDATION_REFRESH_STATE
        recommendation_rationale = (
            "This campaign has accumulated multi-wave gain across more than one bounded quality dimension, the lineage is materially stronger in aggregate, and no higher-value bounded follow-on currently outranks refreshing the revised candidate."
        )
        recommended_follow_on_family = CAMPAIGN_FOLLOW_ON_REVISED_CANDIDATE_REFRESH
        operator_review_recommended = False
    elif progress_recommendation_state == PROGRESS_RECOMMENDATION_REMEDIATE_STATE or strategy_state == STRATEGY_OPEN_TARGETED_REMEDIATION_WAVE_STATE:
        campaign_progress_state = (
            CAMPAIGN_PARTIAL_PROGRESS_STATE
            if accumulated_improved_dimension_ids
            else CAMPAIGN_STAGNATION_STATE
        )
        campaign_state = CAMPAIGN_SHIFT_TO_TARGETED_REMEDIATION_STATE
        recommendation_state = CAMPAIGN_RECOMMENDATION_REMEDIATE_STATE
        recommendation_rationale = (
            "Campaign evidence still shows weak bounded dimensions that need targeted remediation before broader expansion or another revised-candidate refresh."
        )
        recommended_follow_on_family = STRATEGY_FOLLOW_ON_TARGETED_REMEDIATION_WAVE
        operator_review_recommended = False
    elif progress_recommendation_state == PROGRESS_RECOMMENDATION_CONTINUE_STATE and (
        strategy_state == STRATEGY_START_NEXT_QUALITY_WAVE_STATE
        or (
            materially_stronger_in_aggregate
            and len(accumulated_improved_dimension_ids) >= 2
        )
    ):
        campaign_progress_state = (
            CAMPAIGN_PROGRESS_CONTINUES_STATE
            if latest_wave_added_new_dimension or newly_improved_dimension_ids
            else CAMPAIGN_DIMINISHING_RETURNS_STATE
        )
        campaign_state = CAMPAIGN_START_NEXT_QUALITY_WAVE_STATE
        recommendation_state = CAMPAIGN_RECOMMENDATION_NEXT_QUALITY_WAVE_STATE
        recommendation_rationale = (
            "Campaign evidence shows broadening bounded gain across the current reference target lineage, so the next conservative move is another broader quality wave rather than an immediate hold or remediation-only pass."
        )
        recommended_follow_on_family = STRATEGY_FOLLOW_ON_NEXT_QUALITY_WAVE
        operator_review_recommended = False
    elif progress_recommendation_state == PROGRESS_RECOMMENDATION_CONTINUE_STATE or strategy_state == STRATEGY_CONTINUE_REFINING_CURRENT_REFERENCE_TARGET_STATE:
        campaign_progress_state = (
            CAMPAIGN_PROGRESS_CONTINUES_STATE
            if latest_wave_added_new_dimension or newly_improved_dimension_ids
            else CAMPAIGN_PARTIAL_PROGRESS_STATE
        )
        campaign_state = CAMPAIGN_CONTINUE_CURRENT_WAVE_FAMILY_STATE
        recommendation_state = CAMPAIGN_RECOMMENDATION_CONTINUE_STATE
        recommendation_rationale = (
            "Campaign evidence still supports bounded progress on the current wave family, so the next conservative move is to continue the same campaign without broadening authority."
        )
        recommended_follow_on_family = CAMPAIGN_FOLLOW_ON_CURRENT_WAVE_CONTINUATION
        operator_review_recommended = False
    elif progress_recommendation_state == PROGRESS_RECOMMENDATION_HOLD_STATE or strategy_state == STRATEGY_HOLD_CURRENT_REFERENCE_TARGET_STATE:
        campaign_progress_state = (
            CAMPAIGN_CONVERGENCE_STATE
            if campaign_convergence_detected
            else (
                CAMPAIGN_DIMINISHING_RETURNS_STATE
                if campaign_diminishing_returns_detected
                else CAMPAIGN_STAGNATION_STATE
            )
        )
        campaign_state = (
            CAMPAIGN_CONVERGENCE_DETECTED_STATE
            if campaign_convergence_detected
            else CAMPAIGN_HOLD_CURRENT_REFERENCE_TARGET_STATE
        )
        recommendation_state = CAMPAIGN_RECOMMENDATION_HOLD_STATE
        recommendation_rationale = (
            "The current campaign no longer has a higher-value bounded follow-on than holding the current reference target, so NOVALI should hold this lineage pending more evidence."
        )
        recommended_follow_on_family = STRATEGY_FOLLOW_ON_HOLD_CURRENT_REFERENCE
        operator_review_recommended = False
    else:
        campaign_progress_state = (
            CAMPAIGN_DIMINISHING_RETURNS_STATE
            if campaign_diminishing_returns_detected
            else CAMPAIGN_STAGNATION_STATE
        )
        campaign_state = CAMPAIGN_PAUSE_FOR_OPERATOR_REVIEW_STATE
        recommendation_state = CAMPAIGN_RECOMMENDATION_PAUSE_STATE
        recommendation_rationale = (
            "Campaign evidence is no longer moving decisively enough to justify another automatic bounded wave selection, so the safer posture is explicit operator review."
        )
        recommended_follow_on_family = STRATEGY_FOLLOW_ON_PENDING_OPERATOR_REVIEW
        operator_review_recommended = True

    recommended_objective_id = ""
    recommended_objective_class = ""
    recommended_skill_pack_id = ""
    recommended_dimension_id = ""
    recommended_dimension_title = ""
    if recommendation_state in {
        CAMPAIGN_RECOMMENDATION_CONTINUE_STATE,
        CAMPAIGN_RECOMMENDATION_REMEDIATE_STATE,
        CAMPAIGN_RECOMMENDATION_NEXT_QUALITY_WAVE_STATE,
    }:
        recommended_objective_id = str(
            strategy_follow_on_plan.get("recommended_objective_id", "")
        ).strip() or str(
            progress_recommendation.get("recommended_objective_id", "")
        ).strip() or str(quality_next_pack_plan.get("selected_objective_id", "")).strip()
        recommended_objective_class = str(
            strategy_follow_on_plan.get("recommended_objective_class", "")
        ).strip() or str(
            progress_recommendation.get("recommended_objective_class", "")
        ).strip() or str(
            quality_next_pack_plan.get("selected_objective_class", "")
        ).strip()
        if not recommended_objective_class:
            recommended_objective_class = _objective_class_from_objective_id(
                recommended_objective_id
            )
        recommended_skill_pack_id = str(
            strategy_follow_on_plan.get("recommended_skill_pack_id", "")
        ).strip() or str(
            progress_recommendation.get("recommended_skill_pack_id", "")
        ).strip() or str(
            quality_next_pack_plan.get("selected_skill_pack_id", "")
        ).strip()
        recommended_dimension_id = str(
            strategy_follow_on_plan.get("recommended_dimension_id", "")
        ).strip() or str(
            progress_recommendation.get("recommended_dimension_id", "")
        ).strip() or str(
            quality_next_pack_plan.get("selected_dimension_id", "")
        ).strip()
        recommended_dimension_title = str(
            strategy_follow_on_plan.get("recommended_dimension_title", "")
        ).strip() or str(
            progress_recommendation.get("recommended_dimension_title", "")
        ).strip() or str(
            quality_next_pack_plan.get("selected_dimension_title", "")
        ).strip()
    elif recommendation_state == CAMPAIGN_RECOMMENDATION_REFRESH_STATE:
        recommended_objective_id = "prepare_candidate_promotion_bundle"
        recommended_objective_class = "prepare_candidate_promotion_bundle"

    current_campaign["waves"] = waves
    current_campaign["current_campaign_wave_count"] = len(waves)
    current_campaign["last_updated_at"] = _now()
    current_campaign["last_wave_index"] = int(last_wave.get("wave_index", 0) or 0)
    current_campaign["last_wave_strategy_state"] = str(
        last_wave.get("strategy_state", "")
    ).strip()
    current_campaign["last_wave_follow_on_family"] = str(
        last_wave.get("follow_on_family", "")
    ).strip()
    current_campaign["last_wave_skill_pack_id"] = str(
        last_wave.get("selected_skill_pack_id", "")
    ).strip()
    current_campaign["accumulated_improved_dimension_ids"] = list(
        accumulated_improved_dimension_ids
    )
    current_campaign["accumulated_partial_dimension_ids"] = list(
        accumulated_partial_dimension_ids
    )
    current_campaign["remaining_weak_dimension_ids"] = list(weak_dimension_ids)
    current_campaign["materially_stronger_than_reference_target_in_aggregate"] = bool(
        quality_composite_evaluation.get(
            "materially_stronger_than_reference_target_in_aggregate",
            False,
        )
    )
    current_campaign["campaign_progress_state"] = campaign_progress_state
    current_campaign["campaign_state"] = campaign_state
    current_campaign["recommendation_state"] = recommendation_state
    current_campaign["recommended_follow_on_family"] = recommended_follow_on_family
    current_campaign["refresh_revised_candidate_justified"] = bool(
        refresh_revised_candidate_justified
    )
    current_campaign["campaign_rationale"] = recommendation_rationale

    campaigns = preserved_campaigns + [current_campaign]

    campaign_history = {
        "schema_name": SUCCESSOR_CAMPAIGN_HISTORY_SCHEMA_NAME,
        "schema_version": SUCCESSOR_CAMPAIGN_HISTORY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_campaign_id": campaign_id,
        "current_reference_target_id": current_reference_target_id,
        "current_generation_index": int(current_generation_index),
        "current_campaign_wave_count": int(len(waves)),
        "campaigns": campaigns,
    }
    campaign_delta = {
        "schema_name": SUCCESSOR_CAMPAIGN_DELTA_SCHEMA_NAME,
        "schema_version": SUCCESSOR_CAMPAIGN_DELTA_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_campaign_id": campaign_id,
        "current_reference_target_id": current_reference_target_id,
        "current_generation_index": int(current_generation_index),
        "campaign_wave_count": int(len(waves)),
        "last_wave_index": int(last_wave.get("wave_index", 0) or 0),
        "last_wave_strategy_state": str(last_wave.get("strategy_state", "")).strip(),
        "last_wave_follow_on_family": str(
            last_wave.get("follow_on_family", "")
        ).strip(),
        "last_wave_objective_id": str(last_wave.get("objective_id", "")).strip(),
        "last_wave_objective_class": str(
            last_wave.get("objective_class", "")
        ).strip(),
        "last_wave_skill_pack_id": str(
            last_wave.get("selected_skill_pack_id", "")
        ).strip(),
        "last_wave_dimension_id": last_wave_dimension_id,
        "last_wave_improvement_state": str(
            last_wave.get("improvement_state", "")
        ).strip(),
        "latest_wave_added_new_dimension": latest_wave_added_new_dimension,
        "campaign_new_dimension_ids_from_latest_wave": (
            [last_wave_dimension_id] if latest_wave_added_new_dimension else []
        ),
        "accumulated_improved_dimension_ids": accumulated_improved_dimension_ids,
        "remaining_weak_dimension_ids": weak_dimension_ids,
        "regressed_dimension_ids": regressed_dimension_ids,
        "materially_stronger_than_reference_target_in_aggregate": bool(
            quality_composite_evaluation.get(
                "materially_stronger_than_reference_target_in_aggregate",
                False,
            )
        ),
        "campaign_progress_state": campaign_progress_state,
    }
    campaign_governance = {
        "schema_name": SUCCESSOR_CAMPAIGN_GOVERNANCE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_CAMPAIGN_GOVERNANCE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_campaign_id": campaign_id,
        "current_reference_target_id": current_reference_target_id,
        "current_generation_index": int(current_generation_index),
        "campaign_wave_count": int(len(waves)),
        "campaign_progress_state": campaign_progress_state,
        "campaign_state": campaign_state,
        "campaign_state_title": _campaign_state_title(campaign_state),
        "accumulated_improved_dimension_ids": accumulated_improved_dimension_ids,
        "accumulated_partial_dimension_ids": accumulated_partial_dimension_ids,
        "remaining_weak_dimension_ids": weak_dimension_ids,
        "regressed_dimension_ids": regressed_dimension_ids,
        "latest_wave_added_new_dimension": latest_wave_added_new_dimension,
        "refresh_revised_candidate_justified": bool(
            refresh_revised_candidate_justified
        ),
        "campaign_convergence_detected": campaign_convergence_detected,
        "campaign_diminishing_returns_detected": campaign_diminishing_returns_detected,
        "campaign_rationale": recommendation_rationale,
        "evidence_used": {
            "campaign_history_path": str(paths["campaign_history_path"]),
            "generation_history_path": str(paths["generation_history_path"]),
            "generation_delta_path": str(paths["generation_delta_path"]),
            "progress_governance_path": str(paths["progress_governance_path"]),
            "progress_recommendation_path": str(
                paths["progress_recommendation_path"]
            ),
            "strategy_selection_path": str(paths["strategy_selection_path"]),
            "strategy_follow_on_plan_path": str(
                paths["strategy_follow_on_plan_path"]
            ),
            "skill_pack_invocation_path": str(paths["skill_pack_invocation_path"]),
            "skill_pack_result_path": str(paths["skill_pack_result_path"]),
            "quality_improvement_summary_path": str(
                paths["quality_improvement_summary_path"]
            ),
            "quality_composite_evaluation_path": str(
                paths["quality_composite_evaluation_path"]
            ),
            "reference_target_path": str(paths["reference_target_path"]),
            "reference_target_consumption_path": str(
                paths["reference_target_consumption_path"]
            ),
        },
    }
    campaign_recommendation = {
        "schema_name": SUCCESSOR_CAMPAIGN_RECOMMENDATION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_CAMPAIGN_RECOMMENDATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_campaign_id": campaign_id,
        "current_reference_target_id": current_reference_target_id,
        "campaign_progress_state": campaign_progress_state,
        "campaign_state": campaign_state,
        "recommendation_state": recommendation_state,
        "recommendation_title": _campaign_recommendation_title(
            recommendation_state
        ),
        "recommended_follow_on_family": recommended_follow_on_family,
        "recommended_objective_id": recommended_objective_id,
        "recommended_objective_class": recommended_objective_class,
        "recommended_skill_pack_id": recommended_skill_pack_id,
        "recommended_dimension_id": recommended_dimension_id,
        "recommended_dimension_title": recommended_dimension_title,
        "operator_review_required": operator_review_recommended,
        "refresh_revised_candidate_justified": bool(
            refresh_revised_candidate_justified
        ),
        "baseline_mutation_performed": False,
        "rationale": recommendation_rationale,
    }
    campaign_wave_plan = {
        "schema_name": SUCCESSOR_CAMPAIGN_WAVE_PLAN_SCHEMA_NAME,
        "schema_version": SUCCESSOR_CAMPAIGN_WAVE_PLAN_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "current_campaign_id": campaign_id,
        "current_reference_target_id": current_reference_target_id,
        "campaign_state": campaign_state,
        "campaign_state_title": _campaign_state_title(campaign_state),
        "recommendation_state": recommendation_state,
        "recommended_follow_on_family": recommended_follow_on_family,
        "recommended_follow_on_title": _campaign_follow_on_title(
            recommended_follow_on_family
        ),
        "recommended_objective_id": recommended_objective_id,
        "recommended_objective_class": recommended_objective_class,
        "recommended_skill_pack_id": recommended_skill_pack_id,
        "recommended_dimension_id": recommended_dimension_id,
        "recommended_dimension_title": recommended_dimension_title,
        "operator_review_recommended_before_execution": operator_review_recommended,
        "execution_readiness_state": (
            "ready_for_bounded_follow_on"
            if recommendation_state
            in {
                CAMPAIGN_RECOMMENDATION_CONTINUE_STATE,
                CAMPAIGN_RECOMMENDATION_REMEDIATE_STATE,
                CAMPAIGN_RECOMMENDATION_NEXT_QUALITY_WAVE_STATE,
                CAMPAIGN_RECOMMENDATION_REFRESH_STATE,
            }
            and not operator_review_recommended
            else (
                "pending_operator_review"
                if operator_review_recommended
                else "hold_without_immediate_follow_on"
            )
        ),
        "bounded_execution_scope": "active_workspace_only",
        "refresh_revised_candidate_justified": bool(
            refresh_revised_candidate_justified
        ),
        "rationale": recommendation_rationale,
        "baseline_mutation_performed": False,
    }
    return {
        "campaign_history": campaign_history,
        "campaign_delta": campaign_delta,
        "campaign_governance": campaign_governance,
        "campaign_recommendation": campaign_recommendation,
        "campaign_wave_plan": campaign_wave_plan,
    }


def _materialize_successor_campaign_governance_outputs(
    *,
    workspace_root: Path,
    runtime_event_log_path: Path | None = None,
    session_id: str = "",
    directive_id: str = "",
    execution_profile: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    outputs = _evaluate_successor_campaign_governance_state(workspace_root=workspace_root)
    if not outputs:
        return {
            "campaign_history": load_json(paths["campaign_history_path"]),
            "campaign_delta": load_json(paths["campaign_delta_path"]),
            "campaign_governance": load_json(paths["campaign_governance_path"]),
            "campaign_recommendation": load_json(
                paths["campaign_recommendation_path"]
            ),
            "campaign_wave_plan": load_json(paths["campaign_wave_plan_path"]),
            "campaign_history_path": str(paths["campaign_history_path"]),
            "campaign_delta_path": str(paths["campaign_delta_path"]),
            "campaign_governance_path": str(paths["campaign_governance_path"]),
            "campaign_recommendation_path": str(
                paths["campaign_recommendation_path"]
            ),
            "campaign_wave_plan_path": str(paths["campaign_wave_plan_path"]),
        }

    write_rows = [
        (
            paths["campaign_history_path"],
            dict(outputs.get("campaign_history", {})),
            "successor_campaign_history_json",
        ),
        (
            paths["campaign_delta_path"],
            dict(outputs.get("campaign_delta", {})),
            "successor_campaign_delta_json",
        ),
        (
            paths["campaign_governance_path"],
            dict(outputs.get("campaign_governance", {})),
            "successor_campaign_governance_json",
        ),
        (
            paths["campaign_recommendation_path"],
            dict(outputs.get("campaign_recommendation", {})),
            "successor_campaign_recommendation_json",
        ),
        (
            paths["campaign_wave_plan_path"],
            dict(outputs.get("campaign_wave_plan", {})),
            "successor_campaign_wave_plan_json",
        ),
    ]
    if runtime_event_log_path and str(runtime_event_log_path) not in {"", "."}:
        for artifact_path, artifact_payload, artifact_kind in write_rows:
            _write_json(
                artifact_path,
                artifact_payload,
                log_path=runtime_event_log_path,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=workspace_id,
                workspace_root=str(workspace_root),
                work_item_id="successor_campaign_governance",
                artifact_kind=artifact_kind,
            )
        _event(
            runtime_event_log_path,
            event_type="successor_campaign_governance_recorded",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            generation_index=int(
                dict(outputs.get("campaign_history", {})).get(
                    "current_generation_index", 0
                )
                or 0
            ),
            campaign_id=str(
                dict(outputs.get("campaign_history", {})).get("current_campaign_id", "")
            ),
            campaign_wave_count=int(
                dict(outputs.get("campaign_history", {})).get(
                    "current_campaign_wave_count", 0
                )
                or 0
            ),
            campaign_progress_state=str(
                dict(outputs.get("campaign_governance", {})).get(
                    "campaign_progress_state", ""
                )
            ),
            campaign_recommendation_state=str(
                dict(outputs.get("campaign_recommendation", {})).get(
                    "recommendation_state", ""
                )
            ),
            campaign_follow_on_family=str(
                dict(outputs.get("campaign_wave_plan", {})).get(
                    "recommended_follow_on_family", ""
                )
            ),
            refresh_revised_candidate_justified=bool(
                dict(outputs.get("campaign_governance", {})).get(
                    "refresh_revised_candidate_justified", False
                )
            ),
            campaign_history_path=str(paths["campaign_history_path"]),
            campaign_delta_path=str(paths["campaign_delta_path"]),
            campaign_governance_path=str(paths["campaign_governance_path"]),
            campaign_recommendation_path=str(paths["campaign_recommendation_path"]),
            campaign_wave_plan_path=str(paths["campaign_wave_plan_path"]),
        )
    else:
        for artifact_path, artifact_payload, _artifact_kind in write_rows:
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    _sync_campaign_governance_to_latest_artifacts(
        workspace_root=workspace_root,
        paths=paths,
        campaign_history=dict(outputs.get("campaign_history", {})),
        campaign_delta=dict(outputs.get("campaign_delta", {})),
        campaign_governance=dict(outputs.get("campaign_governance", {})),
        campaign_recommendation=dict(outputs.get("campaign_recommendation", {})),
        campaign_wave_plan=dict(outputs.get("campaign_wave_plan", {})),
    )
    return {
        **outputs,
        "campaign_history_path": str(paths["campaign_history_path"]),
        "campaign_delta_path": str(paths["campaign_delta_path"]),
        "campaign_governance_path": str(paths["campaign_governance_path"]),
        "campaign_recommendation_path": str(paths["campaign_recommendation_path"]),
        "campaign_wave_plan_path": str(paths["campaign_wave_plan_path"]),
    }


def _materialize_successor_strategy_follow_on_handoff(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    review_outputs: dict[str, Any],
    reseed_outputs: dict[str, Any],
    strategy_selection_outputs: dict[str, Any],
    runtime_event_log_path: Path | None = None,
    session_id: str = "",
    directive_id: str = "",
    execution_profile: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    strategy_selection = dict(strategy_selection_outputs.get("strategy_selection", {}))
    strategy_rationale = dict(strategy_selection_outputs.get("strategy_rationale", {}))
    follow_on_plan = dict(strategy_selection_outputs.get("strategy_follow_on_plan", {}))
    selected_strategy_state = str(
        strategy_selection.get("selected_strategy_state", "")
    ).strip()
    follow_on_family = str(follow_on_plan.get("follow_on_family", "")).strip()
    recommended_objective_id = str(
        follow_on_plan.get("recommended_objective_id", "")
    ).strip()
    recommended_objective_class = str(
        follow_on_plan.get("recommended_objective_class", "")
    ).strip() or _objective_class_from_objective_id(recommended_objective_id)
    recommended_skill_pack_id = str(
        follow_on_plan.get("recommended_skill_pack_id", "")
    ).strip()
    recommended_dimension_id = str(
        follow_on_plan.get("recommended_dimension_id", "")
    ).strip()
    recommended_dimension_title = str(
        follow_on_plan.get("recommended_dimension_title", "")
    ).strip()
    executable_strategy = selected_strategy_state in {
        STRATEGY_CONTINUE_REFINING_CURRENT_REFERENCE_TARGET_STATE,
        STRATEGY_OPEN_TARGETED_REMEDIATION_WAVE_STATE,
        STRATEGY_START_NEXT_QUALITY_WAVE_STATE,
    }
    if not executable_strategy or not recommended_objective_id:
        return {
            "review_outputs": review_outputs,
            "reseed_outputs": reseed_outputs,
            "strategy_follow_on_materialized": False,
        }

    next_objective_proposal = dict(review_outputs.get("next_objective_proposal", {}))
    current_proposal_id = str(next_objective_proposal.get("objective_id", "")).strip()
    current_proposal_state = str(
        next_objective_proposal.get("proposal_state", "")
    ).strip()
    reseed_request = dict(reseed_outputs.get("request", {}))
    reseed_proposed_objective_id = str(
        reseed_request.get("proposed_objective_id", "")
    ).strip()
    should_refresh_proposal = (
        current_proposal_id != recommended_objective_id
        or current_proposal_state != NEXT_OBJECTIVE_AVAILABLE_STATE
    )
    should_refresh_reseed = (
        should_refresh_proposal or reseed_proposed_objective_id != recommended_objective_id
    )
    if not should_refresh_proposal and not should_refresh_reseed:
        return {
            "review_outputs": review_outputs,
            "reseed_outputs": reseed_outputs,
            "strategy_follow_on_materialized": False,
        }

    review_summary = dict(review_outputs.get("review_summary", {}))
    promotion_recommendation = dict(review_outputs.get("promotion_recommendation", {}))
    review_pack, _review_source = _load_internal_knowledge_pack(
        session=session,
        source_id=INTERNAL_SUCCESSOR_PROMOTION_REVIEW_SOURCE_ID,
        expected_schema_name=SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    objective_template = dict(
        _objective_template_rows(review_pack).get(recommended_objective_id, {})
    )
    proposal_payload = {
        "schema_name": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME,
        "schema_version": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(
            review_summary.get("directive_id", current_directive.get("directive_id", ""))
        ).strip(),
        "completed_objective_id": str(
            review_summary.get("completed_objective_id", "")
        ).strip(),
        "completed_objective_source_kind": str(
            review_summary.get("completed_objective_source_kind", "")
        ).strip(),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "proposal_state": NEXT_OBJECTIVE_AVAILABLE_STATE,
        "proposal_source": "strategy_follow_on",
        "objective_id": recommended_objective_id,
        "objective_class": recommended_objective_class,
        "title": str(objective_template.get("title", "")).strip()
        or str(follow_on_plan.get("recommended_objective_title", "")).strip()
        or _humanize_objective_id(recommended_objective_id),
        "rationale": (
            "The current generational evidence selected an explicit bounded strategy follow-on. "
            f"Selected strategy: `{selected_strategy_state or '<unknown>'}`. "
            f"Follow-on family: `{follow_on_family or '<unknown>'}`. "
            f"Target dimension: `{recommended_dimension_title or recommended_dimension_id or '<unknown>'}`. "
            f"Bounded skill pack: `{recommended_skill_pack_id or '<unknown>'}`. "
            f"Reference target: `{str(strategy_selection.get('current_reference_target_id', '')).strip() or 'current_bounded_baseline_expectations_v1'}`. "
            + str(
                strategy_rationale.get(
                    "selected_strategy_rationale",
                    follow_on_plan.get("rationale", ""),
                )
            ).strip()
        ),
        "promotion_recommendation_state": str(
            promotion_recommendation.get("promotion_recommendation_state", "")
        ),
        "operator_review_required": True,
        "authorized_for_automatic_execution": False,
        "bounded_objective_complete": bool(
            review_summary.get("bounded_objective_complete", True)
        ),
        "strategy_selection_state": selected_strategy_state,
        "strategy_follow_on_family": follow_on_family,
        "strategy_selection_path": str(paths["strategy_selection_path"]),
        "strategy_follow_on_plan_path": str(paths["strategy_follow_on_plan_path"]),
        "selected_quality_dimension_id": recommended_dimension_id,
        "selected_quality_dimension_title": recommended_dimension_title,
        "selected_skill_pack_id": recommended_skill_pack_id,
        "active_bounded_reference_target_id": str(
            strategy_selection.get("current_reference_target_id", "")
        ).strip(),
    }
    if runtime_event_log_path and str(runtime_event_log_path) not in {"", "."}:
        _write_json(
            paths["next_objective_proposal_path"],
            proposal_payload,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id or str(workspace_root.name),
            workspace_root=str(workspace_root),
            work_item_id="successor_strategy_follow_on",
            artifact_kind="successor_next_objective_proposal_json",
        )
        _event(
            runtime_event_log_path,
            event_type="successor_strategy_follow_on_materialized",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id or str(workspace_root.name),
            workspace_root=str(workspace_root),
            strategy_state=selected_strategy_state,
            follow_on_family=follow_on_family,
            proposed_objective_id=recommended_objective_id,
            strategy_selection_path=str(paths["strategy_selection_path"]),
            strategy_follow_on_plan_path=str(paths["strategy_follow_on_plan_path"]),
            next_objective_proposal_path=str(paths["next_objective_proposal_path"]),
        )
    else:
        paths["next_objective_proposal_path"].parent.mkdir(parents=True, exist_ok=True)
        paths["next_objective_proposal_path"].write_text(
            _dump(proposal_payload),
            encoding="utf-8",
        )

    updated_review_outputs = {
        **review_outputs,
        "next_objective_proposal": proposal_payload,
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
    }
    if runtime_event_log_path and str(runtime_event_log_path) not in {"", "."}:
        updated_reseed_outputs = _materialize_successor_reseed_request_outputs(
            current_directive=current_directive,
            workspace_root=workspace_root,
            review_outputs=updated_review_outputs,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id or str(workspace_root.name),
        )
    else:
        updated_reseed_outputs = _build_pending_reseed_outputs(
            current_directive=current_directive,
            workspace_root=workspace_root,
            review_outputs=updated_review_outputs,
        )
        for artifact_path, artifact_payload in (
            (paths["reseed_request_path"], dict(updated_reseed_outputs.get("request", {}))),
            (paths["reseed_decision_path"], dict(updated_reseed_outputs.get("decision", {}))),
            (
                paths["continuation_lineage_path"],
                dict(updated_reseed_outputs.get("continuation_lineage", {})),
            ),
            (
                paths["effective_next_objective_path"],
                dict(updated_reseed_outputs.get("effective_next_objective", {})),
            ),
        ):
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    return {
        "review_outputs": updated_review_outputs,
        "reseed_outputs": updated_reseed_outputs,
        "strategy_follow_on_materialized": True,
        "next_objective_proposal": proposal_payload,
    }


def _materialize_successor_campaign_follow_on_handoff(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    review_outputs: dict[str, Any],
    reseed_outputs: dict[str, Any],
    campaign_governance_outputs: dict[str, Any],
    runtime_event_log_path: Path | None = None,
    session_id: str = "",
    directive_id: str = "",
    execution_profile: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    campaign_governance = dict(
        campaign_governance_outputs.get("campaign_governance", {})
    )
    campaign_recommendation = dict(
        campaign_governance_outputs.get("campaign_recommendation", {})
    )
    campaign_wave_plan = dict(campaign_governance_outputs.get("campaign_wave_plan", {}))
    recommendation_state = str(
        campaign_recommendation.get("recommendation_state", "")
    ).strip()
    follow_on_family = str(
        campaign_wave_plan.get("recommended_follow_on_family", "")
    ).strip() or str(campaign_recommendation.get("recommended_follow_on_family", "")).strip()
    recommended_objective_id = str(
        campaign_wave_plan.get("recommended_objective_id", "")
    ).strip() or str(campaign_recommendation.get("recommended_objective_id", "")).strip()
    recommended_objective_class = str(
        campaign_wave_plan.get("recommended_objective_class", "")
    ).strip() or str(
        campaign_recommendation.get("recommended_objective_class", "")
    ).strip() or _objective_class_from_objective_id(recommended_objective_id)
    executable_campaign = (
        recommendation_state == CAMPAIGN_RECOMMENDATION_REFRESH_STATE
        and follow_on_family == CAMPAIGN_FOLLOW_ON_REVISED_CANDIDATE_REFRESH
    )
    if not executable_campaign or not recommended_objective_id:
        return {
            "review_outputs": review_outputs,
            "reseed_outputs": reseed_outputs,
            "campaign_follow_on_materialized": False,
        }

    next_objective_proposal = dict(review_outputs.get("next_objective_proposal", {}))
    current_proposal_id = str(next_objective_proposal.get("objective_id", "")).strip()
    current_proposal_state = str(
        next_objective_proposal.get("proposal_state", "")
    ).strip()
    current_proposal_source = str(
        next_objective_proposal.get("proposal_source", "")
    ).strip()
    reseed_request = dict(reseed_outputs.get("request", {}))
    reseed_proposed_objective_id = str(
        reseed_request.get("proposed_objective_id", "")
    ).strip()
    should_refresh_proposal = (
        current_proposal_id != recommended_objective_id
        or current_proposal_state != NEXT_OBJECTIVE_AVAILABLE_STATE
        or current_proposal_source != "campaign_follow_on"
    )
    should_refresh_reseed = (
        should_refresh_proposal or reseed_proposed_objective_id != recommended_objective_id
    )
    if not should_refresh_proposal and not should_refresh_reseed:
        return {
            "review_outputs": review_outputs,
            "reseed_outputs": reseed_outputs,
            "campaign_follow_on_materialized": False,
        }

    review_summary = dict(review_outputs.get("review_summary", {}))
    promotion_recommendation = dict(review_outputs.get("promotion_recommendation", {}))
    review_pack, _review_source = _load_internal_knowledge_pack(
        session=session,
        source_id=INTERNAL_SUCCESSOR_PROMOTION_REVIEW_SOURCE_ID,
        expected_schema_name=SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    objective_template = dict(
        _objective_template_rows(review_pack).get(recommended_objective_id, {})
    )
    proposal_payload = {
        "schema_name": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME,
        "schema_version": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(
            review_summary.get("directive_id", current_directive.get("directive_id", ""))
        ).strip(),
        "completed_objective_id": str(
            review_summary.get("completed_objective_id", "")
        ).strip(),
        "completed_objective_source_kind": str(
            review_summary.get("completed_objective_source_kind", "")
        ).strip(),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "proposal_state": NEXT_OBJECTIVE_AVAILABLE_STATE,
        "proposal_source": "campaign_follow_on",
        "objective_id": recommended_objective_id,
        "objective_class": recommended_objective_class,
        "title": str(objective_template.get("title", "")).strip()
        or str(campaign_wave_plan.get("recommended_follow_on_title", "")).strip()
        or _humanize_objective_id(recommended_objective_id),
        "rationale": (
            "The accumulated bounded campaign evidence now justifies a revised-candidate refresh. "
            f"Campaign recommendation: `{recommendation_state or '<unknown>'}`. "
            f"Campaign follow-on family: `{follow_on_family or '<unknown>'}`. "
            f"Campaign state: `{str(campaign_governance.get('campaign_state', '')).strip() or '<unknown>'}`. "
            f"Campaign wave count: `{int(campaign_governance.get('campaign_wave_count', 0) or 0)}`. "
            f"Reference target: `{str(campaign_recommendation.get('current_reference_target_id', '')).strip() or 'current_bounded_baseline_expectations_v1'}`. "
            + str(campaign_recommendation.get("rationale", "")).strip()
        ),
        "promotion_recommendation_state": str(
            promotion_recommendation.get("promotion_recommendation_state", "")
        ),
        "operator_review_required": True,
        "authorized_for_automatic_execution": False,
        "bounded_objective_complete": bool(
            review_summary.get("bounded_objective_complete", True)
        ),
        "campaign_recommendation_state": recommendation_state,
        "campaign_follow_on_family": follow_on_family,
        "campaign_recommendation_path": str(paths["campaign_recommendation_path"]),
        "campaign_wave_plan_path": str(paths["campaign_wave_plan_path"]),
        "campaign_governance_path": str(paths["campaign_governance_path"]),
        "current_campaign_id": str(
            campaign_recommendation.get("current_campaign_id", "")
        ).strip(),
        "active_bounded_reference_target_id": str(
            campaign_recommendation.get("current_reference_target_id", "")
        ).strip(),
    }
    if runtime_event_log_path and str(runtime_event_log_path) not in {"", "."}:
        _write_json(
            paths["next_objective_proposal_path"],
            proposal_payload,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id or str(workspace_root.name),
            workspace_root=str(workspace_root),
            work_item_id="successor_campaign_follow_on",
            artifact_kind="successor_next_objective_proposal_json",
        )
        _event(
            runtime_event_log_path,
            event_type="successor_campaign_follow_on_materialized",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id or str(workspace_root.name),
            workspace_root=str(workspace_root),
            campaign_recommendation_state=recommendation_state,
            campaign_follow_on_family=follow_on_family,
            proposed_objective_id=recommended_objective_id,
            campaign_recommendation_path=str(paths["campaign_recommendation_path"]),
            campaign_wave_plan_path=str(paths["campaign_wave_plan_path"]),
            next_objective_proposal_path=str(paths["next_objective_proposal_path"]),
        )
    else:
        paths["next_objective_proposal_path"].parent.mkdir(parents=True, exist_ok=True)
        paths["next_objective_proposal_path"].write_text(
            _dump(proposal_payload),
            encoding="utf-8",
        )

    updated_review_outputs = {
        **review_outputs,
        "next_objective_proposal": proposal_payload,
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
    }
    if runtime_event_log_path and str(runtime_event_log_path) not in {"", "."}:
        updated_reseed_outputs = _materialize_successor_reseed_request_outputs(
            current_directive=current_directive,
            workspace_root=workspace_root,
            review_outputs=updated_review_outputs,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id or str(workspace_root.name),
        )
    else:
        updated_reseed_outputs = _build_pending_reseed_outputs(
            current_directive=current_directive,
            workspace_root=workspace_root,
            review_outputs=updated_review_outputs,
        )
        for artifact_path, artifact_payload in (
            (paths["reseed_request_path"], dict(updated_reseed_outputs.get("request", {}))),
            (paths["reseed_decision_path"], dict(updated_reseed_outputs.get("decision", {}))),
            (
                paths["continuation_lineage_path"],
                dict(updated_reseed_outputs.get("continuation_lineage", {})),
            ),
            (
                paths["effective_next_objective_path"],
                dict(updated_reseed_outputs.get("effective_next_objective", {})),
            ),
        ):
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    return {
        "review_outputs": updated_review_outputs,
        "reseed_outputs": updated_reseed_outputs,
        "campaign_follow_on_materialized": True,
        "next_objective_proposal": proposal_payload,
    }


def _materialize_successor_campaign_cycle_follow_on_handoff(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    review_outputs: dict[str, Any],
    reseed_outputs: dict[str, Any],
    campaign_cycle_governance_outputs: dict[str, Any],
    runtime_event_log_path: Path | None = None,
    session_id: str = "",
    directive_id: str = "",
    execution_profile: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    campaign_cycle_governance = dict(
        campaign_cycle_governance_outputs.get("campaign_cycle_governance", {})
    )
    campaign_cycle_recommendation = dict(
        campaign_cycle_governance_outputs.get("campaign_cycle_recommendation", {})
    )
    campaign_cycle_follow_on_plan = dict(
        campaign_cycle_governance_outputs.get("campaign_cycle_follow_on_plan", {})
    )
    recommendation_state = str(
        campaign_cycle_recommendation.get("recommendation_state", "")
    ).strip()
    follow_on_family = str(
        campaign_cycle_follow_on_plan.get("recommended_follow_on_family", "")
    ).strip() or str(
        campaign_cycle_recommendation.get("recommended_follow_on_family", "")
    ).strip()
    recommended_objective_id = str(
        campaign_cycle_follow_on_plan.get("recommended_objective_id", "")
    ).strip() or str(
        campaign_cycle_recommendation.get("recommended_objective_id", "")
    ).strip()
    recommended_objective_class = str(
        campaign_cycle_follow_on_plan.get("recommended_objective_class", "")
    ).strip() or str(
        campaign_cycle_recommendation.get("recommended_objective_class", "")
    ).strip() or _objective_class_from_objective_id(recommended_objective_id)
    recommended_skill_pack_id = str(
        campaign_cycle_follow_on_plan.get("recommended_skill_pack_id", "")
    ).strip() or str(
        campaign_cycle_recommendation.get("recommended_skill_pack_id", "")
    ).strip()
    recommended_dimension_id = str(
        campaign_cycle_follow_on_plan.get("recommended_dimension_id", "")
    ).strip() or str(
        campaign_cycle_recommendation.get("recommended_dimension_id", "")
    ).strip()
    recommended_dimension_title = str(
        campaign_cycle_follow_on_plan.get("recommended_dimension_title", "")
    ).strip() or str(
        campaign_cycle_recommendation.get("recommended_dimension_title", "")
    ).strip()
    executable_campaign_cycle = recommendation_state in {
        CAMPAIGN_CYCLE_RECOMMENDATION_START_STATE,
        CAMPAIGN_CYCLE_RECOMMENDATION_REMEDIATE_STATE,
    }
    if not executable_campaign_cycle or not recommended_objective_id:
        return {
            "review_outputs": review_outputs,
            "reseed_outputs": reseed_outputs,
            "campaign_cycle_follow_on_materialized": False,
        }

    next_objective_proposal = dict(review_outputs.get("next_objective_proposal", {}))
    current_proposal_id = str(next_objective_proposal.get("objective_id", "")).strip()
    current_proposal_state = str(
        next_objective_proposal.get("proposal_state", "")
    ).strip()
    current_proposal_source = str(
        next_objective_proposal.get("proposal_source", "")
    ).strip()
    reseed_request = dict(reseed_outputs.get("request", {}))
    reseed_proposed_objective_id = str(
        reseed_request.get("proposed_objective_id", "")
    ).strip()
    should_refresh_proposal = (
        current_proposal_id != recommended_objective_id
        or current_proposal_state != NEXT_OBJECTIVE_AVAILABLE_STATE
        or current_proposal_source != "campaign_cycle_follow_on"
    )
    should_refresh_reseed = (
        should_refresh_proposal or reseed_proposed_objective_id != recommended_objective_id
    )
    if not should_refresh_proposal and not should_refresh_reseed:
        return {
            "review_outputs": review_outputs,
            "reseed_outputs": reseed_outputs,
            "campaign_cycle_follow_on_materialized": False,
        }

    review_summary = dict(review_outputs.get("review_summary", {}))
    promotion_recommendation = dict(review_outputs.get("promotion_recommendation", {}))
    review_pack, _review_source = _load_internal_knowledge_pack(
        session=session,
        source_id=INTERNAL_SUCCESSOR_PROMOTION_REVIEW_SOURCE_ID,
        expected_schema_name=SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_NAME,
        expected_schema_version=SUCCESSOR_PROMOTION_REVIEW_KNOWLEDGE_PACK_SCHEMA_VERSION,
    )
    objective_template = dict(
        _objective_template_rows(review_pack).get(recommended_objective_id, {})
    )
    proposal_payload = {
        "schema_name": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_NAME,
        "schema_version": SUCCESSOR_NEXT_OBJECTIVE_PROPOSAL_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": str(
            review_summary.get("directive_id", current_directive.get("directive_id", ""))
        ).strip(),
        "completed_objective_id": str(
            review_summary.get("completed_objective_id", "")
        ).strip(),
        "completed_objective_source_kind": str(
            review_summary.get("completed_objective_source_kind", "")
        ).strip(),
        "workspace_id": str(workspace_root.name),
        "workspace_root": str(workspace_root),
        "proposal_state": NEXT_OBJECTIVE_AVAILABLE_STATE,
        "proposal_source": "campaign_cycle_follow_on",
        "objective_id": recommended_objective_id,
        "objective_class": recommended_objective_class,
        "title": str(objective_template.get("title", "")).strip()
        or _humanize_objective_id(recommended_objective_id),
        "rationale": (
            "The current cycle-over-cycle evidence selected an explicit bounded campaign-cycle follow-on. "
            f"Campaign-cycle recommendation: `{recommendation_state or '<unknown>'}`. "
            f"Campaign-cycle follow-on family: `{follow_on_family or '<unknown>'}`. "
            f"Target dimension: `{recommended_dimension_title or recommended_dimension_id or '<unknown>'}`. "
            f"Bounded skill pack: `{recommended_skill_pack_id or '<unknown>'}`. "
            f"Campaign-cycle index: `{int(campaign_cycle_recommendation.get('current_campaign_cycle_index', 0) or 0)}`. "
            f"Reference target: `{str(campaign_cycle_recommendation.get('current_reference_target_id', '')).strip() or 'current_bounded_baseline_expectations_v1'}`. "
            + str(campaign_cycle_recommendation.get("rationale", "")).strip()
        ),
        "promotion_recommendation_state": str(
            promotion_recommendation.get("promotion_recommendation_state", "")
        ),
        "operator_review_required": True,
        "authorized_for_automatic_execution": False,
        "bounded_objective_complete": bool(
            review_summary.get("bounded_objective_complete", True)
        ),
        "campaign_cycle_recommendation_state": recommendation_state,
        "campaign_cycle_follow_on_family": follow_on_family,
        "campaign_cycle_recommendation_path": str(
            paths["campaign_cycle_recommendation_path"]
        ),
        "campaign_cycle_follow_on_plan_path": str(
            paths["campaign_cycle_follow_on_plan_path"]
        ),
        "campaign_cycle_governance_path": str(paths["campaign_cycle_governance_path"]),
        "current_campaign_cycle_id": str(
            campaign_cycle_recommendation.get("current_campaign_cycle_id", "")
        ).strip(),
        "current_campaign_cycle_index": int(
            campaign_cycle_recommendation.get("current_campaign_cycle_index", 0) or 0
        ),
        "selected_quality_dimension_id": recommended_dimension_id,
        "selected_quality_dimension_title": recommended_dimension_title,
        "selected_skill_pack_id": recommended_skill_pack_id,
        "active_bounded_reference_target_id": str(
            campaign_cycle_recommendation.get("current_reference_target_id", "")
        ).strip(),
    }
    if runtime_event_log_path and str(runtime_event_log_path) not in {"", "."}:
        _write_json(
            paths["next_objective_proposal_path"],
            proposal_payload,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id or str(workspace_root.name),
            workspace_root=str(workspace_root),
            work_item_id="successor_campaign_cycle_follow_on",
            artifact_kind="successor_next_objective_proposal_json",
        )
        _event(
            runtime_event_log_path,
            event_type="successor_campaign_cycle_follow_on_materialized",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id or str(workspace_root.name),
            workspace_root=str(workspace_root),
            campaign_cycle_recommendation_state=recommendation_state,
            campaign_cycle_follow_on_family=follow_on_family,
            proposed_objective_id=recommended_objective_id,
            campaign_cycle_recommendation_path=str(
                paths["campaign_cycle_recommendation_path"]
            ),
            campaign_cycle_follow_on_plan_path=str(
                paths["campaign_cycle_follow_on_plan_path"]
            ),
            next_objective_proposal_path=str(paths["next_objective_proposal_path"]),
        )
    else:
        paths["next_objective_proposal_path"].parent.mkdir(parents=True, exist_ok=True)
        paths["next_objective_proposal_path"].write_text(
            _dump(proposal_payload),
            encoding="utf-8",
        )

    updated_review_outputs = {
        **review_outputs,
        "next_objective_proposal": proposal_payload,
        "next_objective_proposal_path": str(paths["next_objective_proposal_path"]),
    }
    if runtime_event_log_path and str(runtime_event_log_path) not in {"", "."}:
        updated_reseed_outputs = _materialize_successor_reseed_request_outputs(
            current_directive=current_directive,
            workspace_root=workspace_root,
            review_outputs=updated_review_outputs,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id or str(workspace_root.name),
        )
    else:
        updated_reseed_outputs = _build_pending_reseed_outputs(
            current_directive=current_directive,
            workspace_root=workspace_root,
            review_outputs=updated_review_outputs,
        )
        for artifact_path, artifact_payload in (
            (paths["reseed_request_path"], dict(updated_reseed_outputs.get("request", {}))),
            (paths["reseed_decision_path"], dict(updated_reseed_outputs.get("decision", {}))),
            (
                paths["continuation_lineage_path"],
                dict(updated_reseed_outputs.get("continuation_lineage", {})),
            ),
            (
                paths["effective_next_objective_path"],
                dict(updated_reseed_outputs.get("effective_next_objective", {})),
            ),
        ):
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    return {
        "review_outputs": updated_review_outputs,
        "reseed_outputs": updated_reseed_outputs,
        "campaign_cycle_follow_on_materialized": True,
        "next_objective_proposal": proposal_payload,
    }


def _evaluate_successor_campaign_cycle_governance_state(
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    generation_history = load_json(paths["generation_history_path"])
    generation_delta = load_json(paths["generation_delta_path"])
    progress_governance = load_json(paths["progress_governance_path"])
    progress_recommendation = load_json(paths["progress_recommendation_path"])
    campaign_history = load_json(paths["campaign_history_path"])
    campaign_recommendation = load_json(paths["campaign_recommendation_path"])
    campaign_wave_plan = load_json(paths["campaign_wave_plan_path"])
    reference_target = load_json(paths["reference_target_path"])
    reference_target_consumption = load_json(paths["reference_target_consumption_path"])
    quality_next_pack_plan = load_json(paths["quality_next_pack_plan_path"])
    quality_priority_matrix = load_json(paths["quality_priority_matrix_path"])

    current_reference_target_id = str(
        reference_target.get("preferred_reference_target_id", "")
    ).strip() or str(generation_history.get("current_admitted_candidate_id", "")).strip()
    if not current_reference_target_id:
        return {}

    directive_id = str(generation_history.get("directive_id", "")).strip() or str(
        reference_target.get("directive_id", "")
    ).strip() or str(campaign_history.get("directive_id", "")).strip()
    protected_live_baseline_reference_id = str(
        reference_target_consumption.get("protected_live_baseline_reference_id", "")
    ).strip() or str(
        reference_target.get("protected_live_baseline_reference_id", "")
    ).strip() or "current_bounded_baseline_expectations_v1"
    generation_rows = [
        dict(item)
        for item in list(generation_history.get("generations", []))
        if isinstance(item, dict)
        and str(item.get("admitted_candidate_id", "")).strip()
    ]
    generation_rows.sort(key=lambda item: int(item.get("generation_index", 0) or 0))
    nonhistorical_rows = [
        dict(item)
        for item in generation_rows
        if str(item.get("candidate_variant", "")).strip()
        != "historical_lineage_reference"
    ]
    if not nonhistorical_rows:
        return {}

    campaign_rows = [
        dict(item)
        for item in list(campaign_history.get("campaigns", []))
        if isinstance(item, dict)
    ]
    campaign_rows_by_reference_target = {
        str(item.get("reference_target_id", "")).strip(): dict(item)
        for item in campaign_rows
        if str(item.get("reference_target_id", "")).strip()
    }
    prior_reference_target_hint = str(
        reference_target.get("supersedes_reference_target_id", "")
    ).strip() or str(reference_target.get("prior_reference_target_id", "")).strip()

    cycle_rows: list[dict[str, Any]] = []
    for index, row in enumerate(nonhistorical_rows, start=1):
        resulting_reference_target_id = str(
            row.get("admitted_candidate_id", "")
        ).strip() or str(row.get("reference_target_id", "")).strip()
        if not resulting_reference_target_id:
            continue
        if index > 1:
            prior_row = dict(nonhistorical_rows[index - 2])
        else:
            prior_row = next(
                (
                    dict(item)
                    for item in reversed(generation_rows)
                    if int(item.get("generation_index", 0) or 0)
                    < int(row.get("generation_index", 0) or 0)
                    and str(item.get("admitted_candidate_id", "")).strip()
                    != resulting_reference_target_id
                ),
                {},
            )
        prior_reference_target_id = str(
            prior_row.get("admitted_candidate_id", "")
        ).strip() or str(row.get("prior_admitted_candidate_id", "")).strip()
        if not prior_reference_target_id and resulting_reference_target_id == current_reference_target_id:
            prior_reference_target_id = prior_reference_target_hint

        source_campaign = dict(
            campaign_rows_by_reference_target.get(prior_reference_target_id, {})
        )
        source_campaign_id = str(source_campaign.get("campaign_id", "")).strip()
        source_campaign_wave_count = int(
            source_campaign.get(
                "current_campaign_wave_count",
                len(list(source_campaign.get("waves", []))),
            )
            or 0
        )
        closing_campaign_recommendation_state = str(
            source_campaign.get("recommendation_state", "")
        ).strip()
        closing_campaign_recommendation_source = "campaign_history"
        if not closing_campaign_recommendation_state and str(
            row.get("reference_target_rollover_state", "")
        ).strip() == "rolled_forward_to_revised_candidate":
            closing_campaign_recommendation_state = CAMPAIGN_RECOMMENDATION_REFRESH_STATE
            closing_campaign_recommendation_source = "reference_target_rollover_inference"
        if not closing_campaign_recommendation_state:
            closing_campaign_recommendation_source = "not_available"

        cycle_rows.append(
            {
                "campaign_cycle_id": f"campaign_cycle::{resulting_reference_target_id}",
                "campaign_cycle_index": index,
                "directive_id": directive_id,
                "workspace_id": str(workspace_root.name),
                "workspace_root": str(workspace_root),
                "resulting_reference_target_id": resulting_reference_target_id,
                "prior_reference_target_id": prior_reference_target_id,
                "resulting_generation_index": int(row.get("generation_index", 0) or 0),
                "resulting_candidate_bundle_identity": str(
                    row.get("candidate_bundle_identity", "")
                ).strip(),
                "resulting_candidate_variant": str(
                    row.get("candidate_variant", "")
                ).strip(),
                "reference_target_rollover_state": str(
                    row.get("reference_target_rollover_state", "")
                ).strip(),
                "cycle_quality_composite_state": str(
                    row.get("quality_composite_state", "")
                ).strip(),
                "cycle_materially_stronger_in_aggregate": bool(
                    row.get("materially_stronger_in_aggregate", False)
                ),
                "cycle_improved_dimension_ids": _unique_string_list(
                    list(row.get("improved_dimension_ids", []))
                ),
                "cycle_remaining_weak_dimension_ids": _unique_string_list(
                    list(row.get("weak_dimension_ids", []))
                ),
                "source_campaign_id": source_campaign_id,
                "source_campaign_reference_target_id": str(
                    source_campaign.get("reference_target_id", "")
                ).strip(),
                "source_campaign_wave_count": source_campaign_wave_count,
                "source_campaign_state": str(
                    source_campaign.get("campaign_state", "")
                ).strip(),
                "source_campaign_progress_state": str(
                    source_campaign.get("campaign_progress_state", "")
                ).strip(),
                "source_campaign_accumulated_improved_dimension_ids": _unique_string_list(
                    list(source_campaign.get("accumulated_improved_dimension_ids", []))
                    or list(row.get("improved_dimension_ids", []))
                ),
                "source_campaign_remaining_weak_dimension_ids": _unique_string_list(
                    list(source_campaign.get("remaining_weak_dimension_ids", []))
                    or list(row.get("weak_dimension_ids", []))
                ),
                "source_campaign_last_wave_strategy_state": str(
                    source_campaign.get("last_wave_strategy_state", "")
                ).strip(),
                "source_campaign_last_wave_skill_pack_id": str(
                    source_campaign.get("last_wave_skill_pack_id", "")
                ).strip(),
                "closing_campaign_recommendation_state": (
                    closing_campaign_recommendation_state
                ),
                "closing_campaign_recommendation_source": (
                    closing_campaign_recommendation_source
                ),
                "cycle_closed_by_refresh_rollover": bool(
                    str(row.get("reference_target_rollover_state", "")).strip()
                    == "rolled_forward_to_revised_candidate"
                ),
                "protected_live_baseline_reference_id": (
                    protected_live_baseline_reference_id
                ),
                "baseline_mutation_performed": False,
            }
        )

    if not cycle_rows:
        return {}

    current_cycle_row = next(
        (
            dict(item)
            for item in cycle_rows
            if str(item.get("resulting_reference_target_id", "")).strip()
            == current_reference_target_id
        ),
        dict(cycle_rows[-1]),
    )
    current_cycle_index = int(current_cycle_row.get("campaign_cycle_index", 0) or 0)
    prior_cycle_row = next(
        (
            dict(item)
            for item in reversed(cycle_rows)
            if int(item.get("campaign_cycle_index", 0) or 0) < current_cycle_index
        ),
        {},
    )

    current_improved = set(
        _unique_string_list(
            list(current_cycle_row.get("cycle_improved_dimension_ids", []))
        )
    )
    current_weak = set(
        _unique_string_list(
            list(current_cycle_row.get("cycle_remaining_weak_dimension_ids", []))
        )
    )
    prior_improved = set(
        _unique_string_list(list(prior_cycle_row.get("cycle_improved_dimension_ids", [])))
    )
    prior_weak = set(
        _unique_string_list(
            list(prior_cycle_row.get("cycle_remaining_weak_dimension_ids", []))
        )
    )
    new_dimension_ids_vs_prior_cycle = sorted(
        current_improved - prior_improved if prior_cycle_row else current_improved
    )
    repeated_dimension_ids_vs_prior_cycle = sorted(current_improved.intersection(prior_improved))
    resolved_weak_dimension_ids_vs_prior_cycle = sorted(prior_weak - current_weak)
    regressed_dimension_ids = sorted(prior_improved.intersection(current_weak))
    current_rank = _quality_composite_rank(
        str(current_cycle_row.get("cycle_quality_composite_state", "")).strip()
    )
    prior_rank = _quality_composite_rank(
        str(prior_cycle_row.get("cycle_quality_composite_state", "")).strip()
    )
    breadth_delta_vs_prior_cycle = int(len(current_improved) - len(prior_improved))
    current_cycle_materially_stronger = bool(
        current_cycle_row.get("cycle_materially_stronger_in_aggregate", False)
    )
    prior_cycle_materially_stronger = bool(
        prior_cycle_row.get("cycle_materially_stronger_in_aggregate", False)
    )
    materially_stronger_than_prior_cycle_in_aggregate = bool(
        current_cycle_materially_stronger
        and not regressed_dimension_ids
        and (not prior_cycle_row or current_rank >= prior_rank)
    )

    selected_objective_id = str(
        progress_recommendation.get("recommended_objective_id", "")
    ).strip() or str(quality_next_pack_plan.get("selected_objective_id", "")).strip() or str(
        campaign_recommendation.get("recommended_objective_id", "")
    ).strip() or str(campaign_wave_plan.get("recommended_objective_id", "")).strip()
    selected_objective_class = str(
        progress_recommendation.get("recommended_objective_class", "")
    ).strip() or str(
        quality_next_pack_plan.get("selected_objective_class", "")
    ).strip() or str(
        campaign_recommendation.get("recommended_objective_class", "")
    ).strip() or str(campaign_wave_plan.get("recommended_objective_class", "")).strip()
    selected_skill_pack_id = str(
        progress_recommendation.get("recommended_skill_pack_id", "")
    ).strip() or str(quality_next_pack_plan.get("selected_skill_pack_id", "")).strip() or str(
        campaign_recommendation.get("recommended_skill_pack_id", "")
    ).strip()
    selected_dimension_id = str(
        progress_recommendation.get("recommended_dimension_id", "")
    ).strip() or str(quality_next_pack_plan.get("selected_dimension_id", "")).strip() or str(
        quality_priority_matrix.get("weakest_dimension_id", "")
    ).strip()
    selected_dimension_title = str(
        progress_recommendation.get("recommended_dimension_title", "")
    ).strip() or str(quality_next_pack_plan.get("selected_dimension_title", "")).strip() or str(
        quality_priority_matrix.get("weakest_dimension_title", "")
    ).strip()
    fallback_dimension_definition: dict[str, Any] = {}
    for candidate_dimension_id in [selected_dimension_id, *list(current_weak)]:
        fallback_dimension_definition = _quality_dimension_definition_for_id(
            candidate_dimension_id
        )
        if fallback_dimension_definition:
            break
    if not selected_dimension_id:
        selected_dimension_id = str(
            fallback_dimension_definition.get("dimension_id", "")
        ).strip()
    if not selected_dimension_title:
        selected_dimension_title = str(
            fallback_dimension_definition.get("title", "")
        ).strip()
    if not selected_objective_class:
        selected_objective_class = str(
            fallback_dimension_definition.get("objective_class", "")
        ).strip()
    if not selected_objective_id and selected_objective_class:
        selected_objective_id = selected_objective_class
    if not selected_skill_pack_id:
        selected_skill_pack_id = str(
            fallback_dimension_definition.get("skill_pack_id", "")
        ).strip()

    current_campaign_recommendation_state = str(
        campaign_recommendation.get("recommendation_state", "")
    ).strip()
    current_progress_recommendation_state = str(
        progress_recommendation.get("recommendation_state", "")
    ).strip()
    additional_post_rollover_improvement_supported = bool(
        progress_governance.get("additional_bounded_improvement_justified", False)
        or selected_objective_id
    )

    if regressed_dimension_ids or (
        prior_cycle_row
        and prior_cycle_materially_stronger
        and not current_cycle_materially_stronger
    ) or (prior_cycle_row and current_rank < prior_rank):
        campaign_cycle_progress_state = CAMPAIGN_CYCLE_REGRESSION_STATE
        campaign_cycle_state = CAMPAIGN_CYCLE_REGRESSION_DETECTED_STATE
        recommendation_state = CAMPAIGN_CYCLE_RECOMMENDATION_PAUSE_STATE
        recommended_follow_on_family = STRATEGY_FOLLOW_ON_PENDING_OPERATOR_REVIEW
        operator_review_required = True
        recommendation_rationale = (
            "The newly rolled reference target is weaker than the prior campaign cycle on one or more important bounded dimensions, so the conservative posture is explicit operator review before any further campaigning."
        )
    elif not current_weak and current_cycle_materially_stronger:
        campaign_cycle_progress_state = (
            CAMPAIGN_CYCLE_CONVERGENCE_STATE
            if prior_cycle_row and not new_dimension_ids_vs_prior_cycle
            else CAMPAIGN_CYCLE_PROGRESS_CONTINUES_STATE
        )
        campaign_cycle_state = (
            CAMPAIGN_CYCLE_CONVERGENCE_CONFIRMED_STATE
            if prior_cycle_row and not new_dimension_ids_vs_prior_cycle
            else CAMPAIGN_CYCLE_HOLD_NEW_REFERENCE_TARGET_STATE
        )
        recommendation_state = CAMPAIGN_CYCLE_RECOMMENDATION_HOLD_STATE
        recommended_follow_on_family = CAMPAIGN_CYCLE_FOLLOW_ON_HOLD_NEW_REFERENCE
        operator_review_required = False
        recommendation_rationale = (
            "The rolled reference target remains materially stronger and no bounded weak dimensions remain open, so another full campaign cycle is not justified yet."
        )
    elif current_weak and additional_post_rollover_improvement_supported and (
        current_progress_recommendation_state == PROGRESS_RECOMMENDATION_CONTINUE_STATE
        or current_campaign_recommendation_state
        in {
            CAMPAIGN_RECOMMENDATION_CONTINUE_STATE,
            CAMPAIGN_RECOMMENDATION_NEXT_QUALITY_WAVE_STATE,
        }
    ) and bool(new_dimension_ids_vs_prior_cycle or breadth_delta_vs_prior_cycle > 0):
        campaign_cycle_progress_state = CAMPAIGN_CYCLE_PROGRESS_CONTINUES_STATE
        campaign_cycle_state = CAMPAIGN_CYCLE_START_NEXT_CAMPAIGN_STATE
        recommendation_state = CAMPAIGN_CYCLE_RECOMMENDATION_START_STATE
        recommended_follow_on_family = CAMPAIGN_CYCLE_FOLLOW_ON_NEXT_CAMPAIGN
        operator_review_required = False
        recommendation_rationale = (
            "Cycle-over-cycle evidence still broadens meaningfully and bounded weak dimensions remain, so NOVALI can conservatively open another successor-quality campaign cycle."
        )
    elif current_weak and additional_post_rollover_improvement_supported:
        campaign_cycle_progress_state = (
            CAMPAIGN_CYCLE_PARTIAL_GAIN_STATE
            if new_dimension_ids_vs_prior_cycle
            or resolved_weak_dimension_ids_vs_prior_cycle
            or current_cycle_materially_stronger
            else CAMPAIGN_CYCLE_STAGNATION_STATE
        )
        campaign_cycle_state = (
            CAMPAIGN_CYCLE_TARGETED_POST_ROLLOVER_REMEDIATION_STATE
        )
        recommendation_state = CAMPAIGN_CYCLE_RECOMMENDATION_REMEDIATE_STATE
        recommended_follow_on_family = (
            CAMPAIGN_CYCLE_FOLLOW_ON_TARGETED_POST_ROLLOVER_REMEDIATION
        )
        operator_review_required = False
        recommendation_rationale = (
            "The new rolled target still has narrow bounded weaknesses, so the safer next step is targeted post-rollover remediation rather than immediately opening a broader new campaign."
        )
    elif prior_cycle_row and not new_dimension_ids_vs_prior_cycle:
        campaign_cycle_progress_state = CAMPAIGN_CYCLE_DIMINISHING_RETURNS_STATE
        campaign_cycle_state = CAMPAIGN_CYCLE_DIMINISHING_RETURNS_DETECTED_STATE
        recommendation_state = CAMPAIGN_CYCLE_RECOMMENDATION_OBSERVE_STATE
        recommended_follow_on_family = CAMPAIGN_CYCLE_FOLLOW_ON_OBSERVE
        operator_review_required = False
        recommendation_rationale = (
            "Cycle-over-cycle evidence is no longer broadening meaningfully, so the conservative posture is to observe the new reference target before launching another campaign."
        )
    else:
        campaign_cycle_progress_state = CAMPAIGN_CYCLE_STAGNATION_STATE
        campaign_cycle_state = CAMPAIGN_CYCLE_PAUSE_FOR_OPERATOR_REVIEW_STATE
        recommendation_state = CAMPAIGN_CYCLE_RECOMMENDATION_PAUSE_STATE
        recommended_follow_on_family = STRATEGY_FOLLOW_ON_PENDING_OPERATOR_REVIEW
        operator_review_required = True
        recommendation_rationale = (
            "Cycle-over-cycle evidence is not yet strong or stable enough to justify a new campaign automatically, so explicit operator review is the safer posture."
        )

    recommend_execution = recommendation_state in {
        CAMPAIGN_CYCLE_RECOMMENDATION_START_STATE,
        CAMPAIGN_CYCLE_RECOMMENDATION_REMEDIATE_STATE,
    }
    recommended_objective_id = selected_objective_id if recommend_execution else ""
    recommended_objective_class = (
        selected_objective_class if recommend_execution else ""
    )
    recommended_skill_pack_id = selected_skill_pack_id if recommend_execution else ""
    recommended_dimension_id = selected_dimension_id if recommend_execution else ""
    recommended_dimension_title = selected_dimension_title if recommend_execution else ""
    current_cycle_id = str(current_cycle_row.get("campaign_cycle_id", "")).strip()
    current_cycle_wave_count = int(
        current_cycle_row.get("source_campaign_wave_count", 0) or 0
    )

    return {
        "campaign_cycle_history": {
            "schema_name": SUCCESSOR_CAMPAIGN_CYCLE_HISTORY_SCHEMA_NAME,
            "schema_version": SUCCESSOR_CAMPAIGN_CYCLE_HISTORY_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": str(workspace_root.name),
            "workspace_root": str(workspace_root),
            "current_reference_target_id": current_reference_target_id,
            "prior_reference_target_id": str(
                current_cycle_row.get("prior_reference_target_id", "")
            ).strip(),
            "current_campaign_cycle_id": current_cycle_id,
            "current_campaign_cycle_index": int(current_cycle_index),
            "campaign_cycles": cycle_rows,
        },
        "campaign_cycle_delta": {
            "schema_name": SUCCESSOR_CAMPAIGN_CYCLE_DELTA_SCHEMA_NAME,
            "schema_version": SUCCESSOR_CAMPAIGN_CYCLE_DELTA_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": str(workspace_root.name),
            "workspace_root": str(workspace_root),
            "current_campaign_cycle_id": current_cycle_id,
            "current_campaign_cycle_index": int(current_cycle_index),
            "prior_campaign_cycle_id": str(
                prior_cycle_row.get("campaign_cycle_id", "")
            ).strip(),
            "prior_campaign_cycle_index": int(
                prior_cycle_row.get("campaign_cycle_index", 0) or 0
            ),
            "current_reference_target_id": current_reference_target_id,
            "prior_reference_target_id": str(
                current_cycle_row.get("prior_reference_target_id", "")
            ).strip(),
            "source_campaign_id": str(
                current_cycle_row.get("source_campaign_id", "")
            ).strip(),
            "current_cycle_wave_count": current_cycle_wave_count,
            "prior_cycle_wave_count": int(
                prior_cycle_row.get("source_campaign_wave_count", 0) or 0
            ),
            "current_cycle_improved_dimension_ids": sorted(current_improved),
            "prior_cycle_improved_dimension_ids": sorted(prior_improved),
            "new_dimension_ids_vs_prior_cycle": new_dimension_ids_vs_prior_cycle,
            "repeated_dimension_ids_vs_prior_cycle": repeated_dimension_ids_vs_prior_cycle,
            "resolved_weak_dimension_ids_vs_prior_cycle": (
                resolved_weak_dimension_ids_vs_prior_cycle
            ),
            "regressed_dimension_ids": regressed_dimension_ids,
            "remaining_weak_dimension_ids": sorted(current_weak),
            "breadth_delta_vs_prior_cycle": breadth_delta_vs_prior_cycle,
            "current_cycle_quality_composite_state": str(
                current_cycle_row.get("cycle_quality_composite_state", "")
            ).strip(),
            "prior_cycle_quality_composite_state": str(
                prior_cycle_row.get("cycle_quality_composite_state", "")
            ).strip(),
            "materially_stronger_than_prior_cycle_in_aggregate": (
                materially_stronger_than_prior_cycle_in_aggregate
            ),
            "campaign_cycle_progress_state": campaign_cycle_progress_state,
            "comparison_rationale": recommendation_rationale,
        },
        "campaign_cycle_governance": {
            "schema_name": SUCCESSOR_CAMPAIGN_CYCLE_GOVERNANCE_SCHEMA_NAME,
            "schema_version": SUCCESSOR_CAMPAIGN_CYCLE_GOVERNANCE_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": str(workspace_root.name),
            "workspace_root": str(workspace_root),
            "current_campaign_cycle_id": current_cycle_id,
            "current_campaign_cycle_index": int(current_cycle_index),
            "current_reference_target_id": current_reference_target_id,
            "prior_reference_target_id": str(
                current_cycle_row.get("prior_reference_target_id", "")
            ).strip(),
            "campaign_cycle_progress_state": campaign_cycle_progress_state,
            "campaign_cycle_state": campaign_cycle_state,
            "campaign_cycle_state_title": _campaign_cycle_state_title(
                campaign_cycle_state
            ),
            "current_cycle_wave_count": current_cycle_wave_count,
            "new_dimension_ids_vs_prior_cycle": new_dimension_ids_vs_prior_cycle,
            "repeated_dimension_ids_vs_prior_cycle": repeated_dimension_ids_vs_prior_cycle,
            "resolved_weak_dimension_ids_vs_prior_cycle": (
                resolved_weak_dimension_ids_vs_prior_cycle
            ),
            "remaining_weak_dimension_ids": sorted(current_weak),
            "regressed_dimension_ids": regressed_dimension_ids,
            "campaign_cycle_convergence_detected": bool(
                campaign_cycle_progress_state == CAMPAIGN_CYCLE_CONVERGENCE_STATE
            ),
            "campaign_cycle_diminishing_returns_detected": bool(
                campaign_cycle_progress_state
                == CAMPAIGN_CYCLE_DIMINISHING_RETURNS_STATE
            ),
            "campaign_cycle_rationale": recommendation_rationale,
            "evidence_used": {
                "reference_target_path": str(paths["reference_target_path"]),
                "reference_target_consumption_path": str(
                    paths["reference_target_consumption_path"]
                ),
                "generation_history_path": str(paths["generation_history_path"]),
                "generation_delta_path": str(paths["generation_delta_path"]),
                "progress_governance_path": str(paths["progress_governance_path"]),
                "progress_recommendation_path": str(
                    paths["progress_recommendation_path"]
                ),
                "campaign_history_path": str(paths["campaign_history_path"]),
                "campaign_recommendation_path": str(paths["campaign_recommendation_path"]),
                "campaign_wave_plan_path": str(paths["campaign_wave_plan_path"]),
                "quality_next_pack_plan_path": str(paths["quality_next_pack_plan_path"]),
            },
        },
        "campaign_cycle_recommendation": {
            "schema_name": SUCCESSOR_CAMPAIGN_CYCLE_RECOMMENDATION_SCHEMA_NAME,
            "schema_version": SUCCESSOR_CAMPAIGN_CYCLE_RECOMMENDATION_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": str(workspace_root.name),
            "workspace_root": str(workspace_root),
            "current_campaign_cycle_id": current_cycle_id,
            "current_campaign_cycle_index": int(current_cycle_index),
            "current_reference_target_id": current_reference_target_id,
            "campaign_cycle_progress_state": campaign_cycle_progress_state,
            "campaign_cycle_state": campaign_cycle_state,
            "recommendation_state": recommendation_state,
            "recommendation_title": _campaign_cycle_recommendation_title(
                recommendation_state
            ),
            "recommended_follow_on_family": recommended_follow_on_family,
            "recommended_objective_id": recommended_objective_id,
            "recommended_objective_class": recommended_objective_class,
            "recommended_skill_pack_id": recommended_skill_pack_id,
            "recommended_dimension_id": recommended_dimension_id,
            "recommended_dimension_title": recommended_dimension_title,
            "operator_review_required": operator_review_required,
            "baseline_mutation_performed": False,
            "rationale": recommendation_rationale,
        },
        "campaign_cycle_follow_on_plan": {
            "schema_name": SUCCESSOR_CAMPAIGN_CYCLE_FOLLOW_ON_PLAN_SCHEMA_NAME,
            "schema_version": SUCCESSOR_CAMPAIGN_CYCLE_FOLLOW_ON_PLAN_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": str(workspace_root.name),
            "workspace_root": str(workspace_root),
            "current_campaign_cycle_id": current_cycle_id,
            "current_campaign_cycle_index": int(current_cycle_index),
            "current_reference_target_id": current_reference_target_id,
            "campaign_cycle_state": campaign_cycle_state,
            "campaign_cycle_state_title": _campaign_cycle_state_title(
                campaign_cycle_state
            ),
            "recommendation_state": recommendation_state,
            "recommended_follow_on_family": recommended_follow_on_family,
            "recommended_follow_on_title": _campaign_cycle_follow_on_title(
                recommended_follow_on_family
            ),
            "recommended_objective_id": recommended_objective_id,
            "recommended_objective_class": recommended_objective_class,
            "recommended_skill_pack_id": recommended_skill_pack_id,
            "recommended_dimension_id": recommended_dimension_id,
            "recommended_dimension_title": recommended_dimension_title,
            "operator_review_recommended_before_execution": operator_review_required,
            "execution_readiness_state": (
                "ready_for_bounded_follow_on"
                if recommend_execution and not operator_review_required
                else (
                    "pending_operator_review"
                    if operator_review_required
                    else "hold_without_immediate_follow_on"
                )
            ),
            "bounded_execution_scope": "active_workspace_only",
            "rationale": recommendation_rationale,
            "baseline_mutation_performed": False,
        },
    }


def _materialize_successor_campaign_cycle_governance_outputs(
    *,
    workspace_root: Path,
    runtime_event_log_path: Path | None = None,
    session_id: str = "",
    directive_id: str = "",
    execution_profile: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    outputs = _evaluate_successor_campaign_cycle_governance_state(
        workspace_root=workspace_root
    )
    if not outputs:
        return {
            "campaign_cycle_history": load_json(paths["campaign_cycle_history_path"]),
            "campaign_cycle_delta": load_json(paths["campaign_cycle_delta_path"]),
            "campaign_cycle_governance": load_json(
                paths["campaign_cycle_governance_path"]
            ),
            "campaign_cycle_recommendation": load_json(
                paths["campaign_cycle_recommendation_path"]
            ),
            "campaign_cycle_follow_on_plan": load_json(
                paths["campaign_cycle_follow_on_plan_path"]
            ),
            "campaign_cycle_history_path": str(paths["campaign_cycle_history_path"]),
            "campaign_cycle_delta_path": str(paths["campaign_cycle_delta_path"]),
            "campaign_cycle_governance_path": str(
                paths["campaign_cycle_governance_path"]
            ),
            "campaign_cycle_recommendation_path": str(
                paths["campaign_cycle_recommendation_path"]
            ),
            "campaign_cycle_follow_on_plan_path": str(
                paths["campaign_cycle_follow_on_plan_path"]
            ),
        }

    write_rows = [
        (
            paths["campaign_cycle_history_path"],
            dict(outputs.get("campaign_cycle_history", {})),
            "successor_campaign_cycle_history_json",
        ),
        (
            paths["campaign_cycle_delta_path"],
            dict(outputs.get("campaign_cycle_delta", {})),
            "successor_campaign_cycle_delta_json",
        ),
        (
            paths["campaign_cycle_governance_path"],
            dict(outputs.get("campaign_cycle_governance", {})),
            "successor_campaign_cycle_governance_json",
        ),
        (
            paths["campaign_cycle_recommendation_path"],
            dict(outputs.get("campaign_cycle_recommendation", {})),
            "successor_campaign_cycle_recommendation_json",
        ),
        (
            paths["campaign_cycle_follow_on_plan_path"],
            dict(outputs.get("campaign_cycle_follow_on_plan", {})),
            "successor_campaign_cycle_follow_on_plan_json",
        ),
    ]
    if runtime_event_log_path and str(runtime_event_log_path) not in {"", "."}:
        for artifact_path, artifact_payload, artifact_kind in write_rows:
            _write_json(
                artifact_path,
                artifact_payload,
                log_path=runtime_event_log_path,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=workspace_id,
                workspace_root=str(workspace_root),
                work_item_id="successor_campaign_cycle_governance",
                artifact_kind=artifact_kind,
            )
        _event(
            runtime_event_log_path,
            event_type="successor_campaign_cycle_governance_recorded",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            campaign_cycle_index=int(
                dict(outputs.get("campaign_cycle_history", {})).get(
                    "current_campaign_cycle_index", 0
                )
                or 0
            ),
            campaign_cycle_id=str(
                dict(outputs.get("campaign_cycle_history", {})).get(
                    "current_campaign_cycle_id", ""
                )
            ),
            campaign_cycle_progress_state=str(
                dict(outputs.get("campaign_cycle_governance", {})).get(
                    "campaign_cycle_progress_state", ""
                )
            ),
            campaign_cycle_recommendation_state=str(
                dict(outputs.get("campaign_cycle_recommendation", {})).get(
                    "recommendation_state", ""
                )
            ),
            campaign_cycle_follow_on_family=str(
                dict(outputs.get("campaign_cycle_follow_on_plan", {})).get(
                    "recommended_follow_on_family", ""
                )
            ),
            campaign_cycle_history_path=str(paths["campaign_cycle_history_path"]),
            campaign_cycle_delta_path=str(paths["campaign_cycle_delta_path"]),
            campaign_cycle_governance_path=str(paths["campaign_cycle_governance_path"]),
            campaign_cycle_recommendation_path=str(
                paths["campaign_cycle_recommendation_path"]
            ),
            campaign_cycle_follow_on_plan_path=str(
                paths["campaign_cycle_follow_on_plan_path"]
            ),
        )
    else:
        for artifact_path, artifact_payload, _artifact_kind in write_rows:
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    _sync_campaign_cycle_governance_to_latest_artifacts(
        workspace_root=workspace_root,
        paths=paths,
        campaign_cycle_history=dict(outputs.get("campaign_cycle_history", {})),
        campaign_cycle_delta=dict(outputs.get("campaign_cycle_delta", {})),
        campaign_cycle_governance=dict(outputs.get("campaign_cycle_governance", {})),
        campaign_cycle_recommendation=dict(
            outputs.get("campaign_cycle_recommendation", {})
        ),
        campaign_cycle_follow_on_plan=dict(
            outputs.get("campaign_cycle_follow_on_plan", {})
        ),
    )
    return {
        **outputs,
        "campaign_cycle_history_path": str(paths["campaign_cycle_history_path"]),
        "campaign_cycle_delta_path": str(paths["campaign_cycle_delta_path"]),
        "campaign_cycle_governance_path": str(
            paths["campaign_cycle_governance_path"]
        ),
        "campaign_cycle_recommendation_path": str(
            paths["campaign_cycle_recommendation_path"]
        ),
        "campaign_cycle_follow_on_plan_path": str(
            paths["campaign_cycle_follow_on_plan_path"]
        ),
    }


def _evaluate_successor_loop_governance_state(
    *,
    workspace_root: Path,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    campaign_cycle_history = load_json(paths["campaign_cycle_history_path"])
    campaign_cycle_delta = load_json(paths["campaign_cycle_delta_path"])
    campaign_cycle_governance = load_json(paths["campaign_cycle_governance_path"])
    campaign_cycle_recommendation = load_json(
        paths["campaign_cycle_recommendation_path"]
    )
    campaign_cycle_follow_on_plan = load_json(paths["campaign_cycle_follow_on_plan_path"])
    reference_target = load_json(paths["reference_target_path"])
    reference_target_consumption = load_json(paths["reference_target_consumption_path"])

    current_reference_target_id = str(
        reference_target.get("preferred_reference_target_id", "")
    ).strip() or str(campaign_cycle_history.get("current_reference_target_id", "")).strip()
    if not current_reference_target_id:
        return {}

    directive_id = str(campaign_cycle_history.get("directive_id", "")).strip() or str(
        reference_target.get("directive_id", "")
    ).strip() or str(workspace_root.name)
    protected_live_baseline_reference_id = str(
        reference_target_consumption.get("protected_live_baseline_reference_id", "")
    ).strip() or str(
        reference_target.get("protected_live_baseline_reference_id", "")
    ).strip() or "current_bounded_baseline_expectations_v1"
    prior_reference_target_hint = str(
        reference_target.get("supersedes_reference_target_id", "")
    ).strip() or str(reference_target.get("prior_reference_target_id", "")).strip()

    cycle_rows = [
        dict(item)
        for item in list(campaign_cycle_history.get("campaign_cycles", []))
        if isinstance(item, dict)
    ]
    cycle_rows.sort(key=lambda item: int(item.get("campaign_cycle_index", 0) or 0))

    loop_rows: list[dict[str, Any]] = []
    for row in cycle_rows:
        resulting_reference_target_id = str(
            row.get("resulting_reference_target_id", "")
        ).strip() or str(row.get("reference_target_id", "")).strip()
        if not resulting_reference_target_id:
            continue
        loop_closed_by_refresh_rollover = bool(
            row.get("cycle_closed_by_refresh_rollover", False)
        ) or str(row.get("reference_target_rollover_state", "")).strip() == (
            "rolled_forward_to_revised_candidate"
        )
        if not loop_closed_by_refresh_rollover:
            continue
        prior_reference_target_id = str(
            row.get("prior_reference_target_id", "")
        ).strip()
        if (
            not prior_reference_target_id
            and resulting_reference_target_id == current_reference_target_id
        ):
            prior_reference_target_id = prior_reference_target_hint
        loop_rows.append(
            {
                "loop_id": f"loop::{resulting_reference_target_id}",
                "loop_index": int(row.get("campaign_cycle_index", 0) or 0),
                "directive_id": directive_id,
                "workspace_id": str(workspace_root.name),
                "workspace_root": str(workspace_root),
                "resulting_reference_target_id": resulting_reference_target_id,
                "prior_reference_target_id": prior_reference_target_id,
                "resulting_generation_index": int(
                    row.get("resulting_generation_index", 0) or 0
                ),
                "resulting_candidate_bundle_identity": str(
                    row.get("resulting_candidate_bundle_identity", "")
                ).strip(),
                "resulting_candidate_variant": str(
                    row.get("resulting_candidate_variant", "")
                ).strip(),
                "reference_target_rollover_state": str(
                    row.get("reference_target_rollover_state", "")
                ).strip(),
                "loop_quality_composite_state": str(
                    row.get("cycle_quality_composite_state", "")
                ).strip(),
                "loop_materially_stronger_in_aggregate": bool(
                    row.get("cycle_materially_stronger_in_aggregate", False)
                ),
                "loop_improved_dimension_ids": _unique_string_list(
                    list(row.get("cycle_improved_dimension_ids", []))
                ),
                "loop_remaining_weak_dimension_ids": _unique_string_list(
                    list(row.get("cycle_remaining_weak_dimension_ids", []))
                ),
                "source_campaign_cycle_id": str(
                    row.get("campaign_cycle_id", "")
                ).strip(),
                "source_campaign_id": str(row.get("source_campaign_id", "")).strip(),
                "source_campaign_wave_count": int(
                    row.get("source_campaign_wave_count", 0) or 0
                ),
                "source_campaign_state": str(
                    row.get("source_campaign_state", "")
                ).strip(),
                "source_campaign_progress_state": str(
                    row.get("source_campaign_progress_state", "")
                ).strip(),
                "source_campaign_accumulated_improved_dimension_ids": _unique_string_list(
                    list(row.get("source_campaign_accumulated_improved_dimension_ids", []))
                ),
                "source_campaign_remaining_weak_dimension_ids": _unique_string_list(
                    list(row.get("source_campaign_remaining_weak_dimension_ids", []))
                ),
                "closing_campaign_recommendation_state": str(
                    row.get("closing_campaign_recommendation_state", "")
                ).strip(),
                "closing_campaign_recommendation_source": str(
                    row.get("closing_campaign_recommendation_source", "")
                ).strip(),
                "loop_closed_by_refresh_rollover": loop_closed_by_refresh_rollover,
                "protected_live_baseline_reference_id": (
                    protected_live_baseline_reference_id
                ),
                "baseline_mutation_performed": False,
            }
        )

    if not loop_rows:
        return {}

    current_loop_row = next(
        (
            dict(item)
            for item in loop_rows
            if str(item.get("resulting_reference_target_id", "")).strip()
            == current_reference_target_id
        ),
        dict(loop_rows[-1]),
    )
    current_loop_index = int(current_loop_row.get("loop_index", 0) or 0)
    prior_loop_row = next(
        (
            dict(item)
            for item in reversed(loop_rows)
            if int(item.get("loop_index", 0) or 0) < current_loop_index
        ),
        {},
    )

    current_improved = set(
        _unique_string_list(list(current_loop_row.get("loop_improved_dimension_ids", [])))
    )
    current_weak = set(
        _unique_string_list(
            list(current_loop_row.get("loop_remaining_weak_dimension_ids", []))
        )
    )
    prior_improved = set(
        _unique_string_list(list(prior_loop_row.get("loop_improved_dimension_ids", [])))
    )
    prior_weak = set(
        _unique_string_list(
            list(prior_loop_row.get("loop_remaining_weak_dimension_ids", []))
        )
    )
    new_dimension_ids_vs_prior_loop = sorted(
        current_improved - prior_improved if prior_loop_row else current_improved
    )
    repeated_dimension_ids_vs_prior_loop = sorted(
        current_improved.intersection(prior_improved)
    )
    resolved_weak_dimension_ids_vs_prior_loop = sorted(prior_weak - current_weak)
    regressed_dimension_ids = sorted(prior_improved.intersection(current_weak))
    current_rank = _quality_composite_rank(
        str(current_loop_row.get("loop_quality_composite_state", "")).strip()
    )
    prior_rank = _quality_composite_rank(
        str(prior_loop_row.get("loop_quality_composite_state", "")).strip()
    )
    breadth_delta_vs_prior_loop = int(len(current_improved) - len(prior_improved))
    current_loop_materially_stronger = bool(
        current_loop_row.get("loop_materially_stronger_in_aggregate", False)
    )
    prior_loop_materially_stronger = bool(
        prior_loop_row.get("loop_materially_stronger_in_aggregate", False)
    )
    materially_stronger_than_prior_loop_in_aggregate = bool(
        current_loop_materially_stronger
        and not regressed_dimension_ids
        and (not prior_loop_row or current_rank >= prior_rank)
    )

    current_cycle_recommendation_state = str(
        campaign_cycle_recommendation.get("recommendation_state", "")
    ).strip()
    current_cycle_progress_state = str(
        campaign_cycle_governance.get("campaign_cycle_progress_state", "")
    ).strip()
    selected_objective_id = str(
        campaign_cycle_follow_on_plan.get("recommended_objective_id", "")
    ).strip() or str(
        campaign_cycle_recommendation.get("recommended_objective_id", "")
    ).strip()
    selected_objective_class = str(
        campaign_cycle_follow_on_plan.get("recommended_objective_class", "")
    ).strip() or str(
        campaign_cycle_recommendation.get("recommended_objective_class", "")
    ).strip()
    selected_skill_pack_id = str(
        campaign_cycle_follow_on_plan.get("recommended_skill_pack_id", "")
    ).strip() or str(
        campaign_cycle_recommendation.get("recommended_skill_pack_id", "")
    ).strip()
    selected_dimension_id = str(
        campaign_cycle_follow_on_plan.get("recommended_dimension_id", "")
    ).strip() or str(
        campaign_cycle_recommendation.get("recommended_dimension_id", "")
    ).strip()
    selected_dimension_title = str(
        campaign_cycle_follow_on_plan.get("recommended_dimension_title", "")
    ).strip() or str(
        campaign_cycle_recommendation.get("recommended_dimension_title", "")
    ).strip()
    additional_loop_improvement_supported = bool(
        selected_objective_id
        or current_cycle_recommendation_state
        in {
            CAMPAIGN_CYCLE_RECOMMENDATION_START_STATE,
            CAMPAIGN_CYCLE_RECOMMENDATION_REMEDIATE_STATE,
        }
    )

    if regressed_dimension_ids or (
        prior_loop_row
        and prior_loop_materially_stronger
        and not current_loop_materially_stronger
    ) or (prior_loop_row and current_rank < prior_rank):
        loop_progress_state = LOOP_REGRESSION_STATE
        loop_state = LOOP_REGRESSION_DETECTED_STATE
        recommendation_state = LOOP_RECOMMENDATION_PAUSE_STATE
        recommended_follow_on_family = LOOP_FOLLOW_ON_PENDING_OPERATOR_REVIEW
        operator_review_required = True
        recommendation_rationale = (
            "The latest completed full loop is weaker than the prior loop on one or more important bounded dimensions, so the conservative posture is explicit operator review before any further loop begins."
        )
    elif current_cycle_recommendation_state == CAMPAIGN_CYCLE_RECOMMENDATION_START_STATE and current_weak and additional_loop_improvement_supported:
        loop_progress_state = LOOP_PROGRESS_CONTINUES_STATE
        loop_state = LOOP_START_NEXT_FULL_CAMPAIGN_STATE
        recommendation_state = LOOP_RECOMMENDATION_START_STATE
        recommended_follow_on_family = LOOP_FOLLOW_ON_NEXT_FULL_CAMPAIGN
        operator_review_required = False
        recommendation_rationale = (
            "Loop-over-loop evidence still broadens meaningfully and bounded weak dimensions remain open, so NOVALI can conservatively start another full successor-quality loop."
        )
    elif current_cycle_recommendation_state == CAMPAIGN_CYCLE_RECOMMENDATION_REMEDIATE_STATE and additional_loop_improvement_supported:
        loop_progress_state = (
            LOOP_PARTIAL_GAIN_STATE
            if new_dimension_ids_vs_prior_loop
            or resolved_weak_dimension_ids_vs_prior_loop
            or current_loop_materially_stronger
            else LOOP_STAGNATION_STATE
        )
        loop_state = LOOP_ALLOW_ONLY_TARGETED_REMEDIATION_STATE
        recommendation_state = LOOP_RECOMMENDATION_REMEDIATE_STATE
        recommended_follow_on_family = LOOP_FOLLOW_ON_TARGETED_REMEDIATION
        operator_review_required = False
        recommendation_rationale = (
            "The latest full loop still leaves narrow bounded weaknesses after rollover, so the safer next step is targeted remediation only rather than another full loop."
        )
    elif current_cycle_recommendation_state == CAMPAIGN_CYCLE_RECOMMENDATION_PAUSE_STATE:
        loop_progress_state = (
            LOOP_REGRESSION_STATE
            if regressed_dimension_ids
            else LOOP_STAGNATION_STATE
        )
        loop_state = LOOP_PAUSE_FOR_OPERATOR_REVIEW_STATE
        recommendation_state = LOOP_RECOMMENDATION_PAUSE_STATE
        recommended_follow_on_family = LOOP_FOLLOW_ON_PENDING_OPERATOR_REVIEW
        operator_review_required = True
        recommendation_rationale = (
            "Loop-over-loop evidence is not yet strong or stable enough to justify another full loop automatically, so explicit operator review is the safer posture."
        )
    elif current_cycle_recommendation_state == CAMPAIGN_CYCLE_RECOMMENDATION_OBSERVE_STATE or current_cycle_progress_state == CAMPAIGN_CYCLE_DIMINISHING_RETURNS_STATE:
        loop_progress_state = LOOP_DIMINISHING_RETURNS_STATE
        loop_state = LOOP_DIMINISHING_RETURNS_DETECTED_STATE
        recommendation_state = LOOP_RECOMMENDATION_OBSERVE_STATE
        recommended_follow_on_family = LOOP_FOLLOW_ON_OBSERVE
        operator_review_required = False
        recommendation_rationale = (
            "Loop-over-loop evidence is no longer broadening meaningfully enough to justify another full loop yet, so the conservative posture is to observe the current bounded reference target before restarting."
        )
    elif not current_weak and current_loop_materially_stronger:
        loop_progress_state = (
            LOOP_CONVERGENCE_STATE
            if prior_loop_row and not new_dimension_ids_vs_prior_loop
            else LOOP_PROGRESS_CONTINUES_STATE
        )
        loop_state = (
            LOOP_CONVERGENCE_CONFIRMED_STATE
            if prior_loop_row and not new_dimension_ids_vs_prior_loop
            else LOOP_HOLD_CURRENT_REFERENCE_TARGET_STATE
        )
        recommendation_state = LOOP_RECOMMENDATION_HOLD_STATE
        recommended_follow_on_family = LOOP_FOLLOW_ON_HOLD_CURRENT_REFERENCE
        operator_review_required = False
        recommendation_rationale = (
            "The latest completed full loop produced a materially stronger rolled reference target and no bounded weak dimensions remain open, so the conservative posture is to hold the current bounded target."
        )
    elif current_weak and additional_loop_improvement_supported:
        loop_progress_state = LOOP_PARTIAL_GAIN_STATE
        loop_state = LOOP_ALLOW_ONLY_TARGETED_REMEDIATION_STATE
        recommendation_state = LOOP_RECOMMENDATION_REMEDIATE_STATE
        recommended_follow_on_family = LOOP_FOLLOW_ON_TARGETED_REMEDIATION
        operator_review_required = False
        recommendation_rationale = (
            "The latest full loop did add bounded value, but narrow weaknesses still remain after rollover, so only targeted remediation should be allowed before another full loop."
        )
    else:
        loop_progress_state = LOOP_STAGNATION_STATE
        loop_state = LOOP_PAUSE_FOR_OPERATOR_REVIEW_STATE
        recommendation_state = LOOP_RECOMMENDATION_PAUSE_STATE
        recommended_follow_on_family = LOOP_FOLLOW_ON_PENDING_OPERATOR_REVIEW
        operator_review_required = True
        recommendation_rationale = (
            "Loop-over-loop evidence is too ambiguous to justify another full loop automatically, so explicit operator review is the safer posture."
        )

    recommend_execution = recommendation_state in {
        LOOP_RECOMMENDATION_START_STATE,
        LOOP_RECOMMENDATION_REMEDIATE_STATE,
    }
    recommended_objective_id = selected_objective_id if recommend_execution else ""
    recommended_objective_class = (
        selected_objective_class if recommend_execution else ""
    )
    recommended_skill_pack_id = selected_skill_pack_id if recommend_execution else ""
    recommended_dimension_id = selected_dimension_id if recommend_execution else ""
    recommended_dimension_title = (
        selected_dimension_title if recommend_execution else ""
    )
    current_loop_id = str(current_loop_row.get("loop_id", "")).strip()
    current_loop_wave_count = int(
        current_loop_row.get("source_campaign_wave_count", 0) or 0
    )

    return {
        "loop_history": {
            "schema_name": SUCCESSOR_LOOP_HISTORY_SCHEMA_NAME,
            "schema_version": SUCCESSOR_LOOP_HISTORY_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": str(workspace_root.name),
            "workspace_root": str(workspace_root),
            "current_reference_target_id": current_reference_target_id,
            "prior_reference_target_id": str(
                current_loop_row.get("prior_reference_target_id", "")
            ).strip(),
            "current_loop_id": current_loop_id,
            "current_loop_index": int(current_loop_index),
            "loops": loop_rows,
        },
        "loop_delta": {
            "schema_name": SUCCESSOR_LOOP_DELTA_SCHEMA_NAME,
            "schema_version": SUCCESSOR_LOOP_DELTA_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": str(workspace_root.name),
            "workspace_root": str(workspace_root),
            "current_loop_id": current_loop_id,
            "current_loop_index": int(current_loop_index),
            "prior_loop_id": str(prior_loop_row.get("loop_id", "")).strip(),
            "prior_loop_index": int(prior_loop_row.get("loop_index", 0) or 0),
            "current_reference_target_id": current_reference_target_id,
            "prior_reference_target_id": str(
                current_loop_row.get("prior_reference_target_id", "")
            ).strip(),
            "source_campaign_cycle_id": str(
                current_loop_row.get("source_campaign_cycle_id", "")
            ).strip(),
            "current_loop_wave_count": current_loop_wave_count,
            "prior_loop_wave_count": int(
                prior_loop_row.get("source_campaign_wave_count", 0) or 0
            ),
            "current_loop_improved_dimension_ids": sorted(current_improved),
            "prior_loop_improved_dimension_ids": sorted(prior_improved),
            "new_dimension_ids_vs_prior_loop": new_dimension_ids_vs_prior_loop,
            "repeated_dimension_ids_vs_prior_loop": repeated_dimension_ids_vs_prior_loop,
            "resolved_weak_dimension_ids_vs_prior_loop": (
                resolved_weak_dimension_ids_vs_prior_loop
            ),
            "regressed_dimension_ids": regressed_dimension_ids,
            "remaining_weak_dimension_ids": sorted(current_weak),
            "breadth_delta_vs_prior_loop": breadth_delta_vs_prior_loop,
            "current_loop_quality_composite_state": str(
                current_loop_row.get("loop_quality_composite_state", "")
            ).strip(),
            "prior_loop_quality_composite_state": str(
                prior_loop_row.get("loop_quality_composite_state", "")
            ).strip(),
            "materially_stronger_than_prior_loop_in_aggregate": (
                materially_stronger_than_prior_loop_in_aggregate
            ),
            "loop_progress_state": loop_progress_state,
            "comparison_rationale": recommendation_rationale,
        },
        "loop_governance": {
            "schema_name": SUCCESSOR_LOOP_GOVERNANCE_SCHEMA_NAME,
            "schema_version": SUCCESSOR_LOOP_GOVERNANCE_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": str(workspace_root.name),
            "workspace_root": str(workspace_root),
            "current_loop_id": current_loop_id,
            "current_loop_index": int(current_loop_index),
            "current_reference_target_id": current_reference_target_id,
            "prior_reference_target_id": str(
                current_loop_row.get("prior_reference_target_id", "")
            ).strip(),
            "source_campaign_cycle_id": str(
                current_loop_row.get("source_campaign_cycle_id", "")
            ).strip(),
            "loop_progress_state": loop_progress_state,
            "loop_state": loop_state,
            "loop_state_title": _loop_state_title(loop_state),
            "current_loop_wave_count": current_loop_wave_count,
            "new_dimension_ids_vs_prior_loop": new_dimension_ids_vs_prior_loop,
            "repeated_dimension_ids_vs_prior_loop": repeated_dimension_ids_vs_prior_loop,
            "resolved_weak_dimension_ids_vs_prior_loop": (
                resolved_weak_dimension_ids_vs_prior_loop
            ),
            "remaining_weak_dimension_ids": sorted(current_weak),
            "regressed_dimension_ids": regressed_dimension_ids,
            "loop_convergence_detected": bool(
                loop_progress_state == LOOP_CONVERGENCE_STATE
            ),
            "loop_diminishing_returns_detected": bool(
                loop_progress_state == LOOP_DIMINISHING_RETURNS_STATE
            ),
            "loop_rationale": recommendation_rationale,
            "evidence_used": {
                "reference_target_path": str(paths["reference_target_path"]),
                "reference_target_consumption_path": str(
                    paths["reference_target_consumption_path"]
                ),
                "campaign_cycle_history_path": str(paths["campaign_cycle_history_path"]),
                "campaign_cycle_delta_path": str(paths["campaign_cycle_delta_path"]),
                "campaign_cycle_governance_path": str(
                    paths["campaign_cycle_governance_path"]
                ),
                "campaign_cycle_recommendation_path": str(
                    paths["campaign_cycle_recommendation_path"]
                ),
                "campaign_cycle_follow_on_plan_path": str(
                    paths["campaign_cycle_follow_on_plan_path"]
                ),
            },
        },
        "loop_recommendation": {
            "schema_name": SUCCESSOR_LOOP_RECOMMENDATION_SCHEMA_NAME,
            "schema_version": SUCCESSOR_LOOP_RECOMMENDATION_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": str(workspace_root.name),
            "workspace_root": str(workspace_root),
            "current_loop_id": current_loop_id,
            "current_loop_index": int(current_loop_index),
            "current_reference_target_id": current_reference_target_id,
            "loop_progress_state": loop_progress_state,
            "loop_state": loop_state,
            "recommendation_state": recommendation_state,
            "recommendation_title": _loop_recommendation_title(recommendation_state),
            "recommended_follow_on_family": recommended_follow_on_family,
            "recommended_objective_id": recommended_objective_id,
            "recommended_objective_class": recommended_objective_class,
            "recommended_skill_pack_id": recommended_skill_pack_id,
            "recommended_dimension_id": recommended_dimension_id,
            "recommended_dimension_title": recommended_dimension_title,
            "operator_review_required": operator_review_required,
            "baseline_mutation_performed": False,
            "rationale": recommendation_rationale,
        },
        "loop_follow_on_plan": {
            "schema_name": SUCCESSOR_LOOP_FOLLOW_ON_PLAN_SCHEMA_NAME,
            "schema_version": SUCCESSOR_LOOP_FOLLOW_ON_PLAN_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": str(workspace_root.name),
            "workspace_root": str(workspace_root),
            "current_loop_id": current_loop_id,
            "current_loop_index": int(current_loop_index),
            "current_reference_target_id": current_reference_target_id,
            "loop_state": loop_state,
            "loop_state_title": _loop_state_title(loop_state),
            "recommendation_state": recommendation_state,
            "recommended_follow_on_family": recommended_follow_on_family,
            "recommended_follow_on_title": _loop_follow_on_title(
                recommended_follow_on_family
            ),
            "recommended_objective_id": recommended_objective_id,
            "recommended_objective_class": recommended_objective_class,
            "recommended_skill_pack_id": recommended_skill_pack_id,
            "recommended_dimension_id": recommended_dimension_id,
            "recommended_dimension_title": recommended_dimension_title,
            "operator_review_recommended_before_execution": operator_review_required,
            "execution_readiness_state": (
                "ready_for_bounded_follow_on"
                if recommend_execution and not operator_review_required
                else (
                    "pending_operator_review"
                    if operator_review_required
                    else "hold_without_immediate_follow_on"
                )
            ),
            "bounded_execution_scope": "active_workspace_only",
            "rationale": recommendation_rationale,
            "baseline_mutation_performed": False,
        },
    }


def _materialize_successor_loop_governance_outputs(
    *,
    workspace_root: Path,
    runtime_event_log_path: Path | None = None,
    session_id: str = "",
    directive_id: str = "",
    execution_profile: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    outputs = _evaluate_successor_loop_governance_state(workspace_root=workspace_root)
    if not outputs:
        return {
            "loop_history": load_json(paths["loop_history_path"]),
            "loop_delta": load_json(paths["loop_delta_path"]),
            "loop_governance": load_json(paths["loop_governance_path"]),
            "loop_recommendation": load_json(paths["loop_recommendation_path"]),
            "loop_follow_on_plan": load_json(paths["loop_follow_on_plan_path"]),
            "loop_history_path": str(paths["loop_history_path"]),
            "loop_delta_path": str(paths["loop_delta_path"]),
            "loop_governance_path": str(paths["loop_governance_path"]),
            "loop_recommendation_path": str(paths["loop_recommendation_path"]),
            "loop_follow_on_plan_path": str(paths["loop_follow_on_plan_path"]),
        }

    write_rows = [
        (
            paths["loop_history_path"],
            dict(outputs.get("loop_history", {})),
            "successor_loop_history_json",
        ),
        (
            paths["loop_delta_path"],
            dict(outputs.get("loop_delta", {})),
            "successor_loop_delta_json",
        ),
        (
            paths["loop_governance_path"],
            dict(outputs.get("loop_governance", {})),
            "successor_loop_governance_json",
        ),
        (
            paths["loop_recommendation_path"],
            dict(outputs.get("loop_recommendation", {})),
            "successor_loop_recommendation_json",
        ),
        (
            paths["loop_follow_on_plan_path"],
            dict(outputs.get("loop_follow_on_plan", {})),
            "successor_loop_follow_on_plan_json",
        ),
    ]
    if runtime_event_log_path and str(runtime_event_log_path) not in {"", "."}:
        for artifact_path, artifact_payload, artifact_kind in write_rows:
            _write_json(
                artifact_path,
                artifact_payload,
                log_path=runtime_event_log_path,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=workspace_id,
                workspace_root=str(workspace_root),
                work_item_id="successor_loop_governance",
                artifact_kind=artifact_kind,
            )
        _event(
            runtime_event_log_path,
            event_type="successor_loop_governance_recorded",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            loop_index=int(
                dict(outputs.get("loop_history", {})).get("current_loop_index", 0)
                or 0
            ),
            loop_id=str(dict(outputs.get("loop_history", {})).get("current_loop_id", "")),
            loop_progress_state=str(
                dict(outputs.get("loop_governance", {})).get("loop_progress_state", "")
            ),
            loop_recommendation_state=str(
                dict(outputs.get("loop_recommendation", {})).get(
                    "recommendation_state", ""
                )
            ),
            loop_follow_on_family=str(
                dict(outputs.get("loop_follow_on_plan", {})).get(
                    "recommended_follow_on_family", ""
                )
            ),
            loop_history_path=str(paths["loop_history_path"]),
            loop_delta_path=str(paths["loop_delta_path"]),
            loop_governance_path=str(paths["loop_governance_path"]),
            loop_recommendation_path=str(paths["loop_recommendation_path"]),
            loop_follow_on_plan_path=str(paths["loop_follow_on_plan_path"]),
        )
    else:
        for artifact_path, artifact_payload, _artifact_kind in write_rows:
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(_dump(artifact_payload), encoding="utf-8")

    _sync_loop_governance_to_latest_artifacts(
        workspace_root=workspace_root,
        paths=paths,
        loop_history=dict(outputs.get("loop_history", {})),
        loop_delta=dict(outputs.get("loop_delta", {})),
        loop_governance=dict(outputs.get("loop_governance", {})),
        loop_recommendation=dict(outputs.get("loop_recommendation", {})),
        loop_follow_on_plan=dict(outputs.get("loop_follow_on_plan", {})),
    )
    return {
        **outputs,
        "loop_history_path": str(paths["loop_history_path"]),
        "loop_delta_path": str(paths["loop_delta_path"]),
        "loop_governance_path": str(paths["loop_governance_path"]),
        "loop_recommendation_path": str(paths["loop_recommendation_path"]),
        "loop_follow_on_plan_path": str(paths["loop_follow_on_plan_path"]),
    }


def _quality_gap_blueprint_for_objective(
    *,
    current_objective: dict[str, Any],
    reference_target_context: dict[str, Any],
    skill_pack_manifest: dict[str, Any],
) -> dict[str, Any]:
    objective_id = str(current_objective.get("objective_id", "")).strip()
    objective_class = str(current_objective.get("objective_class", "")).strip()
    skill_pack_id = str(skill_pack_manifest.get("skill_pack_id", "")).strip()
    comparison_basis = str(reference_target_context.get("comparison_basis", "")).strip()
    reference_target_id = str(
        reference_target_context.get("active_bounded_reference_target_id", "")
    ).strip() or str(
        reference_target_context.get("protected_live_baseline_reference_id", "")
    ).strip()
    if skill_pack_id == INTERNAL_SUCCESSOR_WORKSPACE_REVIEW_SKILL_PACK_ID:
        return {
            "quality_gap_id": "workspace_review_depth_gap",
            "title": "Workspace review helper depth",
            "rationale": "The current bounded objective calls for a stronger workspace-local implementation and review helper relative to the active bounded reference target.",
            "weak_areas": [
                {
                    "area_id": "priority_artifact_reporting",
                    "relative_paths": [
                        "src/successor_shell/workspace_contract.py",
                        "tests/test_workspace_contract.py",
                    ],
                    "reason": "The workspace helper should expose clearer priority-artifact reporting and stronger regression coverage.",
                }
            ],
            "comparison_basis": comparison_basis,
            "reference_target_id": reference_target_id,
            "objective_id": objective_id,
            "objective_class": objective_class,
        }
    if skill_pack_id == INTERNAL_SUCCESSOR_TEST_STRENGTHENING_SKILL_PACK_ID:
        return {
            "quality_gap_id": "successor_test_strengthening_gap",
            "title": "Successor regression coverage depth",
            "rationale": "The current bounded objective calls for stronger successor regression coverage relative to the active bounded reference target.",
            "weak_areas": [
                {
                    "area_id": "workspace_contract_regression_depth",
                    "relative_paths": ["tests/test_workspace_contract.py"],
                    "reason": "Workspace-local regression coverage should exercise richer review and artifact-index behaviors.",
                },
                {
                    "area_id": "successor_manifest_regression_depth",
                    "relative_paths": ["tests/test_successor_manifest.py"],
                    "reason": "Successor manifest coverage should exercise readiness grouping and reference-target reporting.",
                },
            ],
            "comparison_basis": comparison_basis,
            "reference_target_id": reference_target_id,
            "objective_id": objective_id,
            "objective_class": objective_class,
        }
    if skill_pack_id == INTERNAL_SUCCESSOR_DOCS_READINESS_SKILL_PACK_ID:
        return {
            "quality_gap_id": "successor_docs_readiness_gap",
            "title": "Successor docs and readiness audit depth",
            "rationale": "The current bounded objective calls for clearer operator-readable readiness documentation relative to the active bounded reference target.",
            "weak_areas": [
                {
                    "area_id": "docs_readiness_review_depth",
                    "relative_paths": [
                        "docs/successor_package_readiness_note.md",
                        "docs/successor_docs_readiness_review.md",
                    ],
                    "reason": "Readiness-facing notes should state what improved, what remains bounded, and how the current successor compares to the admitted candidate reference target.",
                }
            ],
            "comparison_basis": comparison_basis,
            "reference_target_id": reference_target_id,
            "objective_id": objective_id,
            "objective_class": objective_class,
        }
    if skill_pack_id == INTERNAL_SUCCESSOR_ARTIFACT_INDEX_CONSISTENCY_SKILL_PACK_ID:
        return {
            "quality_gap_id": "successor_artifact_index_consistency_gap",
            "title": "Successor artifact index consistency",
            "rationale": "The current bounded objective calls for a clearer artifact index and audit summary relative to the active bounded reference target.",
            "weak_areas": [
                {
                    "area_id": "artifact_index_audit_depth",
                    "relative_paths": [
                        "artifacts/workspace_artifact_index_latest.json",
                        "artifacts/successor_artifact_index_consistency_latest.json",
                    ],
                    "reason": "The bounded workspace should expose a more explicit audit summary for artifact coverage and missing-path consistency.",
                }
            ],
            "comparison_basis": comparison_basis,
            "reference_target_id": reference_target_id,
            "objective_id": objective_id,
            "objective_class": objective_class,
        }
    if skill_pack_id == INTERNAL_SUCCESSOR_HANDOFF_COMPLETENESS_SKILL_PACK_ID:
        return {
            "quality_gap_id": "successor_handoff_completeness_gap",
            "title": "Successor handoff completeness",
            "rationale": "The current bounded objective calls for a more complete admitted-candidate handoff bundle relative to the active bounded reference target.",
            "weak_areas": [
                {
                    "area_id": "handoff_bundle_closeout",
                    "relative_paths": [
                        "docs/successor_promotion_bundle_note.md",
                        "docs/successor_handoff_completeness_note.md",
                        "artifacts/successor_candidate_promotion_bundle_latest.json",
                        "artifacts/successor_admitted_candidate_handoff_latest.json",
                    ],
                    "reason": "The handoff bundle should describe what the admitted candidate contains and how it carries forward without mutating the protected baseline.",
                }
            ],
            "comparison_basis": comparison_basis,
            "reference_target_id": reference_target_id,
            "objective_id": objective_id,
            "objective_class": objective_class,
        }
    return {
        "quality_gap_id": "successor_manifest_coherence_gap",
        "title": "Successor manifest and readiness coherence",
        "rationale": "The current bounded objective calls for a more coherent manifest, readiness note, and delivery summary relative to the active bounded reference target.",
        "weak_areas": [
            {
                "area_id": "manifest_group_coherence",
                "relative_paths": [
                    "src/successor_shell/successor_manifest.py",
                    "tests/test_successor_manifest.py",
                ],
                "reason": "The successor manifest should provide grouped deliverable coverage and explicit missing-path summaries.",
            },
            {
                "area_id": "readiness_artifact_coherence",
                "relative_paths": [
                    "docs/successor_package_readiness_note.md",
                    "artifacts/successor_delivery_manifest_latest.json",
                    "artifacts/successor_readiness_evaluation_latest.json",
                ],
                "reason": "Readiness-facing docs and artifacts should more clearly summarize what is complete and what still remains bounded.",
            },
        ],
        "comparison_basis": comparison_basis,
        "reference_target_id": reference_target_id,
        "objective_id": objective_id,
        "objective_class": objective_class,
    }


def _select_successor_skill_pack(
    *,
    current_directive: dict[str, Any],
    workspace_root: Path,
    session: dict[str, Any],
    cycle_kind: str,
    stage_id: str,
) -> dict[str, Any]:
    current_objective = _current_objective_context(
        current_directive=current_directive,
        workspace_root=workspace_root,
    )
    if str(current_objective.get("source_kind", "")).strip() != OBJECTIVE_SOURCE_APPROVED_RESEED:
        return {}
    objective_class = str(current_objective.get("objective_class", "")).strip()
    skill_pack_id = str(
        SUCCESSOR_SKILL_PACKS_BY_OBJECTIVE_CLASS.get(objective_class, "")
    ).strip()
    if not skill_pack_id:
        return {}
    skill_pack_manifest, skill_pack_source = _load_internal_skill_pack_manifest(
        session=session,
        skill_pack_id=skill_pack_id,
    )
    if not skill_pack_manifest:
        return {}
    allowed_cycle_kinds = {
        str(item).strip()
        for item in list(skill_pack_manifest.get("allowed_cycle_kinds", []))
        if str(item).strip()
    }
    if allowed_cycle_kinds and str(cycle_kind).strip() not in allowed_cycle_kinds:
        return {}
    allowed_stage_ids = {
        str(item).strip()
        for item in list(skill_pack_manifest.get("allowed_stage_ids", []))
        if str(item).strip()
    }
    if allowed_stage_ids and str(stage_id).strip() not in allowed_stage_ids:
        return {}
    reference_target_context = _resolve_reference_target_consumption(
        current_directive=current_directive,
        workspace_root=workspace_root,
        current_objective=current_objective,
    )
    paths = _workspace_paths(workspace_root)
    latest_skill_pack_invocation = load_json(paths["skill_pack_invocation_path"])
    latest_skill_pack_result = load_json(paths["skill_pack_result_path"])
    latest_quality_gap_summary = load_json(paths["quality_gap_summary_path"])
    latest_quality_improvement_summary = load_json(
        paths["quality_improvement_summary_path"]
    )
    roadmap_outputs = _evaluate_successor_quality_roadmap_state(
        workspace_root=workspace_root,
        current_objective=current_objective,
        reference_target_context=reference_target_context,
        latest_skill_pack_invocation=latest_skill_pack_invocation,
        latest_skill_pack_result=latest_skill_pack_result,
        latest_quality_gap_summary=latest_quality_gap_summary,
        latest_quality_improvement_summary=latest_quality_improvement_summary,
    )
    quality_gap_blueprint = _quality_gap_blueprint_for_objective(
        current_objective=current_objective,
        reference_target_context=reference_target_context,
        skill_pack_manifest=skill_pack_manifest,
    )
    next_pack_plan = dict(roadmap_outputs.get("next_pack_plan", {}))
    selected_dimension_id = str(next_pack_plan.get("selected_dimension_id", "")).strip()
    selected_pack_id = str(next_pack_plan.get("selected_skill_pack_id", "")).strip()
    if selected_dimension_id and selected_pack_id == skill_pack_id:
        quality_gap_blueprint["roadmap_dimension_id"] = selected_dimension_id
        quality_gap_blueprint["roadmap_dimension_title"] = str(
            next_pack_plan.get("selected_dimension_title", "")
        ).strip()
        quality_gap_blueprint["roadmap_priority_level"] = str(
            next_pack_plan.get("selected_priority_level", "")
        ).strip()
        quality_gap_blueprint["roadmap_selected_rationale"] = str(
            next_pack_plan.get("selected_rationale", "")
        ).strip()
    return {
        "current_objective": current_objective,
        "reference_target_context": reference_target_context,
        "skill_pack_manifest": skill_pack_manifest,
        "skill_pack_source": skill_pack_source,
        "quality_gap_blueprint": quality_gap_blueprint,
        "roadmap_outputs": roadmap_outputs,
    }


def _invoke_successor_skill_pack(
    *,
    selection: dict[str, Any],
    workspace_root: Path,
    paths: dict[str, Path],
    payload: dict[str, Any],
    cycle_index: int,
    cycle_kind: str,
    stage_id: str,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
) -> dict[str, Any]:
    if not selection:
        return {}
    skill_pack_manifest = dict(selection.get("skill_pack_manifest", {}))
    skill_pack_source = dict(selection.get("skill_pack_source", {}))
    current_objective = dict(selection.get("current_objective", {}))
    reference_target_context = dict(selection.get("reference_target_context", {}))
    quality_gap_blueprint = dict(selection.get("quality_gap_blueprint", {}))
    roadmap_outputs_from_selection = dict(selection.get("roadmap_outputs", {}))
    skill_pack_id = str(skill_pack_manifest.get("skill_pack_id", "")).strip()
    dimension_definition = _quality_dimension_definition_for_skill_pack(skill_pack_id)
    selected_dimension_id = str(
        quality_gap_blueprint.get("roadmap_dimension_id", "")
    ).strip() or str(dimension_definition.get("dimension_id", "")).strip()
    selected_dimension_title = str(
        quality_gap_blueprint.get("roadmap_dimension_title", "")
    ).strip() or str(dimension_definition.get("title", "")).strip()
    selected_dimension_priority_level = str(
        quality_gap_blueprint.get("roadmap_priority_level", "")
    ).strip() or str(dimension_definition.get("priority_level", "")).strip()
    expected_relative_paths = [
        str(item).strip()
        for item in list(skill_pack_manifest.get("expected_output_relative_paths", []))
        if str(item).strip()
    ]
    quality_gap_summary = {
        "schema_name": SUCCESSOR_QUALITY_GAP_SUMMARY_SCHEMA_NAME,
        "schema_version": SUCCESSOR_QUALITY_GAP_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "current_objective": current_objective,
        "selected_skill_pack_id": skill_pack_id,
        "selected_skill_pack_title": str(skill_pack_manifest.get("title", "")).strip(),
        "comparison_basis": str(quality_gap_blueprint.get("comparison_basis", "")).strip(),
        "reference_target_consumption_state": str(
            reference_target_context.get("consumption_state", "")
        ).strip(),
        "active_bounded_reference_target_id": str(
            reference_target_context.get("active_bounded_reference_target_id", "")
        ).strip(),
        "protected_live_baseline_reference_id": str(
            reference_target_context.get("protected_live_baseline_reference_id", "")
        ).strip(),
        "quality_gap_id": str(quality_gap_blueprint.get("quality_gap_id", "")).strip(),
        "quality_gap_title": str(quality_gap_blueprint.get("title", "")).strip(),
        "quality_gap_rationale": str(
            quality_gap_blueprint.get("rationale", "")
        ).strip(),
        "weak_areas": list(quality_gap_blueprint.get("weak_areas", [])),
        "expected_output_relative_paths": expected_relative_paths,
    }
    invocation_payload = {
        "schema_name": SUCCESSOR_SKILL_PACK_INVOCATION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_SKILL_PACK_INVOCATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "cycle_index": int(cycle_index),
        "cycle_kind": str(cycle_kind),
        "stage_id": str(stage_id),
        "current_objective": current_objective,
        "selected_skill_pack_id": skill_pack_id,
        "selected_skill_pack_version": str(
            skill_pack_manifest.get("skill_pack_version", "")
        ).strip(),
        "selected_skill_pack_title": str(skill_pack_manifest.get("title", "")).strip(),
        "capability_class": str(
            skill_pack_manifest.get("capability_class", "")
        ).strip(),
        "selected_reason": str(
            quality_gap_blueprint.get("roadmap_selected_rationale", "")
        ).strip()
        or str(quality_gap_blueprint.get("rationale", "")).strip(),
        "allowed_write_roots": list(payload.get("allowed_write_roots", [])),
        "skill_pack_manifest_path": str(skill_pack_source.get("path_hint", "")),
        "linked_knowledge_pack_ids": list(
            skill_pack_manifest.get("linked_knowledge_pack_ids", [])
        ),
        "reference_target_context": reference_target_context,
        "quality_gap_summary_path": str(paths["quality_gap_summary_path"]),
        "quality_dimension_id": selected_dimension_id,
        "quality_dimension_title": selected_dimension_title,
        "quality_dimension_priority_level": selected_dimension_priority_level,
        "quality_next_pack_plan_path": str(paths["quality_next_pack_plan_path"]),
    }
    _write_json(
        paths["quality_gap_summary_path"],
        quality_gap_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=skill_pack_id,
        artifact_kind="successor_quality_gap_summary_json",
    )
    _write_json(
        paths["skill_pack_invocation_path"],
        invocation_payload,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=skill_pack_id,
        artifact_kind="successor_skill_pack_invocation_json",
    )
    _event(
        runtime_event_log_path,
        event_type="successor_quality_gap_identified",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        quality_gap_id=str(quality_gap_summary.get("quality_gap_id", "")),
        selected_skill_pack_id=skill_pack_id,
        active_bounded_reference_target_id=str(
            reference_target_context.get("active_bounded_reference_target_id", "")
        ),
        quality_gap_summary_path=str(paths["quality_gap_summary_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="successor_skill_pack_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        selected_skill_pack_id=skill_pack_id,
        selected_skill_pack_title=str(skill_pack_manifest.get("title", "")),
        current_objective_id=str(current_objective.get("objective_id", "")),
        current_objective_class=str(current_objective.get("objective_class", "")),
        skill_pack_manifest_path=str(skill_pack_source.get("path_hint", "")),
    )

    changed_paths: list[str] = []
    reference_target_id = str(
        reference_target_context.get("active_bounded_reference_target_id", "")
    ).strip()
    if skill_pack_id == INTERNAL_SUCCESSOR_WORKSPACE_REVIEW_SKILL_PACK_ID:
        _write_text(
            paths["implementation_module_path"],
            _implementation_module_source_with_quality_review(
                directive_id=directive_id,
                reference_target_id=reference_target_id,
            ),
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="skill_pack_workspace_contract_python",
        )
        _write_text(
            paths["implementation_test_path"],
            _implementation_test_source_with_quality_review(),
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="skill_pack_workspace_contract_test_python",
        )
        _write_text(
            paths["implementation_note_path"],
            _workspace_review_iteration_note_text(
                directive_id=directive_id,
                workspace_id=workspace_id,
                reference_target_id=reference_target_id,
            ),
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="skill_pack_workspace_review_note_markdown",
        )
        changed_paths.extend(
            [
                str(paths["implementation_module_path"]),
                str(paths["implementation_test_path"]),
                str(paths["implementation_note_path"]),
            ]
        )
    elif skill_pack_id == INTERNAL_SUCCESSOR_TEST_STRENGTHENING_SKILL_PACK_ID:
        _write_text(
            paths["implementation_test_path"],
            _implementation_test_source_with_quality_review(),
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="skill_pack_workspace_contract_test_python",
        )
        _write_text(
            paths["readiness_test_path"],
            _successor_manifest_test_source_with_quality_pack(),
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="skill_pack_successor_manifest_test_python",
        )
        changed_paths.extend(
            [
                str(paths["implementation_test_path"]),
                str(paths["readiness_test_path"]),
            ]
        )
    elif skill_pack_id == INTERNAL_SUCCESSOR_MANIFEST_QUALITY_SKILL_PACK_ID:
        _write_text(
            paths["readiness_module_path"],
            _successor_manifest_source_with_quality_pack(
                reference_target_id=reference_target_id
            ),
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="skill_pack_successor_manifest_python",
        )
        _write_text(
            paths["readiness_test_path"],
            _successor_manifest_test_source_with_quality_pack(),
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="skill_pack_successor_manifest_test_python",
        )
        _write_text(
            paths["readiness_note_path"],
            _manifest_quality_readiness_note_text(
                directive_id=directive_id,
                workspace_id=workspace_id,
                reference_target_id=reference_target_id,
                deferred_items=[
                    {
                        "item": "protected_surface_mutation",
                        "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
                    },
                    {
                        "item": "live_trusted_source_network_queries",
                        "reason": "trusted-source live network expansion remains deferred in this cycle",
                    },
                ],
            ),
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="skill_pack_successor_readiness_note_markdown",
        )
        changed_paths.extend(
            [
                str(paths["readiness_module_path"]),
                str(paths["readiness_test_path"]),
                str(paths["readiness_note_path"]),
            ]
        )
    elif skill_pack_id == INTERNAL_SUCCESSOR_DOCS_READINESS_SKILL_PACK_ID:
        _write_text(
            paths["readiness_note_path"],
            _manifest_quality_readiness_note_text(
                directive_id=directive_id,
                workspace_id=workspace_id,
                reference_target_id=reference_target_id,
                deferred_items=[
                    {
                        "item": "protected_surface_mutation",
                        "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
                    },
                    {
                        "item": "live_trusted_source_network_queries",
                        "reason": "trusted-source live network expansion remains deferred in this cycle",
                    },
                ],
            ),
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="skill_pack_successor_readiness_note_markdown",
        )
        _write_text(
            paths["docs_readiness_review_path"],
            _docs_readiness_review_text(
                directive_id=directive_id,
                workspace_id=workspace_id,
                reference_target_id=reference_target_id,
            ),
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="skill_pack_successor_docs_readiness_review_markdown",
        )
        changed_paths.extend(
            [
                str(paths["readiness_note_path"]),
                str(paths["docs_readiness_review_path"]),
            ]
        )
    elif skill_pack_id == INTERNAL_SUCCESSOR_ARTIFACT_INDEX_CONSISTENCY_SKILL_PACK_ID:
        artifact_index_consistency = {
            "schema_name": WORKSPACE_ARTIFACT_INDEX_SCHEMA_NAME,
            "schema_version": WORKSPACE_ARTIFACT_INDEX_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": workspace_id,
            "workspace_root": str(workspace_root),
            "reference_target_id": reference_target_id or "current_bounded_baseline_expectations_v1",
            "quality_dimension_id": selected_dimension_id,
            "quality_gap_id": str(quality_gap_blueprint.get("quality_gap_id", "")).strip(),
            "artifact_index_path": str(paths["workspace_artifact_index_path"]),
            "consistency_checks": [
                {
                    "check_id": "workspace_artifact_index_present",
                    "passed": bool(paths["workspace_artifact_index_path"].exists()),
                    "detail": "workspace artifact index is present inside the active workspace",
                },
                {
                    "check_id": "reference_target_consumption_present",
                    "passed": bool(paths["reference_target_consumption_path"].exists()),
                    "detail": "reference-target consumption evidence is present for bounded comparison",
                },
                {
                    "check_id": "quality_artifacts_present",
                    "passed": all(
                        path.exists()
                        for path in (
                            paths["skill_pack_invocation_path"],
                            paths["quality_gap_summary_path"],
                        )
                    ),
                    "detail": "quality-gap and invocation artifacts are available for audit",
                },
            ],
        }
        artifact_index_consistency["all_checks_passed"] = all(
            bool(item.get("passed", False))
            for item in list(artifact_index_consistency.get("consistency_checks", []))
        )
        _write_json(
            paths["artifact_index_consistency_path"],
            artifact_index_consistency,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="skill_pack_successor_artifact_index_consistency_json",
        )
        changed_paths.append(str(paths["artifact_index_consistency_path"]))
    elif skill_pack_id == INTERNAL_SUCCESSOR_HANDOFF_COMPLETENESS_SKILL_PACK_ID:
        _write_text(
            paths["handoff_completeness_note_path"],
            _handoff_completeness_note_text(
                directive_id=directive_id,
                workspace_id=workspace_id,
                reference_target_id=reference_target_id,
            ),
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="skill_pack_successor_handoff_completeness_note_markdown",
        )
        promotion_bundle_manifest = load_json(paths["promotion_bundle_manifest_path"])
        if promotion_bundle_manifest:
            promotion_bundle_manifest["generated_at"] = _now()
            promotion_bundle_manifest["handoff_completeness_reviewed"] = True
            promotion_bundle_manifest["handoff_completeness_note_path"] = str(
                paths["handoff_completeness_note_path"]
            )
            promotion_bundle_manifest["reference_target_id"] = (
                reference_target_id or "current_bounded_baseline_expectations_v1"
            )
            _write_json(
                paths["promotion_bundle_manifest_path"],
                promotion_bundle_manifest,
                log_path=runtime_event_log_path,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=workspace_id,
                workspace_root=str(workspace_root),
                work_item_id=skill_pack_id,
                artifact_kind="successor_candidate_promotion_bundle_json",
            )
            changed_paths.append(str(paths["promotion_bundle_manifest_path"]))
        changed_paths.append(str(paths["handoff_completeness_note_path"]))

    workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    _write_json(
        paths["workspace_artifact_index_path"],
        workspace_artifact_index,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=skill_pack_id,
        artifact_kind="workspace_artifact_index_json",
    )
    changed_paths.append(str(paths["workspace_artifact_index_path"]))

    if skill_pack_id == INTERNAL_SUCCESSOR_MANIFEST_QUALITY_SKILL_PACK_ID:
        delivery_manifest = {
            "schema_name": SUCCESSOR_DELIVERY_MANIFEST_SCHEMA_NAME,
            "schema_version": SUCCESSOR_DELIVERY_MANIFEST_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": workspace_id,
            "workspace_root": str(workspace_root),
            "reference_target_id": reference_target_id,
            "deliverables": [
                {
                    "relative_path": relative_path,
                    "absolute_path": str(workspace_root / relative_path),
                    "present": bool((workspace_root / relative_path).exists()),
                }
                for relative_path in (
                    "plans/bounded_work_cycle_plan.md",
                    "docs/mutable_shell_successor_design_note.md",
                    "plans/successor_continuation_gap_analysis.md",
                    "src/successor_shell/workspace_contract.py",
                    "tests/test_workspace_contract.py",
                    "src/successor_shell/successor_manifest.py",
                    "tests/test_successor_manifest.py",
                    "docs/successor_package_readiness_note.md",
                )
            ],
        }
        delivery_manifest["completion_ready"] = all(
            bool(item.get("present", False))
            for item in list(delivery_manifest.get("deliverables", []))
        )
        _write_json(
            paths["delivery_manifest_path"],
            delivery_manifest,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="successor_delivery_manifest_json",
        )
        readiness_evaluation = {
            "schema_name": SUCCESSOR_READINESS_EVALUATION_SCHEMA_NAME,
            "schema_version": SUCCESSOR_READINESS_EVALUATION_SCHEMA_VERSION,
            "generated_at": _now(),
            "directive_id": directive_id,
            "workspace_id": workspace_id,
            "workspace_root": str(workspace_root),
            "cycle_kind": str(cycle_kind),
            "implementation_bundle_kind": "successor_manifest_quality_bundle",
            "completion_ready": bool(delivery_manifest.get("completion_ready", False)),
            "delivery_manifest_path": str(paths["delivery_manifest_path"]),
            "reference_target_id": reference_target_id,
            "created_files": changed_paths,
            "deferred_items": [],
            "next_recommended_cycle": "operator_review_required",
            "readiness_summary": "Applied the bounded successor manifest quality pack to improve grouped readiness coverage and manifest coherence.",
        }
        _write_json(
            paths["readiness_summary_path"],
            readiness_evaluation,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=skill_pack_id,
            artifact_kind="successor_readiness_evaluation_json",
        )
        changed_paths.extend(
            [
                str(paths["delivery_manifest_path"]),
                str(paths["readiness_summary_path"]),
            ]
        )

    if skill_pack_id == INTERNAL_SUCCESSOR_WORKSPACE_REVIEW_SKILL_PACK_ID:
        result_summary = (
            "Applied the bounded workspace-review skill pack to strengthen workspace-local review helpers and regression coverage."
        )
    elif skill_pack_id == INTERNAL_SUCCESSOR_TEST_STRENGTHENING_SKILL_PACK_ID:
        result_summary = (
            "Applied the bounded successor test-strengthening pack to deepen regression coverage relative to the active bounded reference target."
        )
    elif skill_pack_id == INTERNAL_SUCCESSOR_DOCS_READINESS_SKILL_PACK_ID:
        result_summary = (
            "Applied the bounded docs/readiness pack to strengthen operator-readable readiness documentation relative to the active bounded reference target."
        )
    elif skill_pack_id == INTERNAL_SUCCESSOR_ARTIFACT_INDEX_CONSISTENCY_SKILL_PACK_ID:
        result_summary = (
            "Applied the bounded artifact-index consistency pack to improve auditability and artifact coverage summaries inside the active workspace."
        )
    elif skill_pack_id == INTERNAL_SUCCESSOR_HANDOFF_COMPLETENESS_SKILL_PACK_ID:
        result_summary = (
            "Applied the bounded handoff-completeness pack to improve the admitted-candidate handoff summary without mutating the protected baseline."
        )
    else:
        result_summary = (
            "Applied the bounded successor skill pack inside the active workspace."
        )

    expected_output_paths = [
        str(workspace_root / relative_path) for relative_path in expected_relative_paths
    ]
    planned_artifact_paths = {
        str(paths["skill_pack_result_path"]),
        str(paths["quality_improvement_summary_path"]),
    }
    expected_outputs_present = all(
        Path(path).exists() or path in planned_artifact_paths for path in expected_output_paths
    )
    result_state = "complete" if expected_outputs_present else "partial"
    preview_result_payload = {
        "selected_skill_pack_id": skill_pack_id,
        "selected_skill_pack_title": str(skill_pack_manifest.get("title", "")).strip(),
        "result_state": result_state,
    }
    pre_run_dimension_state = QUALITY_DIMENSION_WEAK_STATE
    for item in list(
        dict(roadmap_outputs_from_selection.get("roadmap", {})).get(
            "tracked_dimensions",
            [],
        )
    ):
        if str(item.get("dimension_id", "")).strip() == selected_dimension_id:
            pre_run_dimension_state = str(item.get("state", "")).strip() or pre_run_dimension_state
            break
    preview_improvement_payload = {
        "selected_skill_pack_id": skill_pack_id,
        "selected_skill_pack_title": str(skill_pack_manifest.get("title", "")).strip(),
        "quality_gap_id": str(quality_gap_blueprint.get("quality_gap_id", "")).strip(),
        "quality_gap_title": str(quality_gap_blueprint.get("title", "")).strip(),
        "improvement_state": result_state,
        "improved_relative_to_reference_target": bool(reference_target_id),
    }
    roadmap_preview = _evaluate_successor_quality_roadmap_state(
        workspace_root=workspace_root,
        current_objective=current_objective,
        reference_target_context=reference_target_context,
        latest_skill_pack_invocation=invocation_payload,
        latest_skill_pack_result=preview_result_payload,
        latest_quality_gap_summary=quality_gap_summary,
        latest_quality_improvement_summary=preview_improvement_payload,
    )
    roadmap_preview_row = {}
    for item in list(dict(roadmap_preview.get("roadmap", {})).get("tracked_dimensions", [])):
        if str(item.get("dimension_id", "")).strip() == selected_dimension_id:
            roadmap_preview_row = dict(item)
            break
    result_payload = {
        "schema_name": SUCCESSOR_SKILL_PACK_RESULT_SCHEMA_NAME,
        "schema_version": SUCCESSOR_SKILL_PACK_RESULT_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "cycle_index": int(cycle_index),
        "selected_skill_pack_id": skill_pack_id,
        "selected_skill_pack_title": str(skill_pack_manifest.get("title", "")).strip(),
        "result_state": result_state,
        "expected_outputs_present": expected_outputs_present,
        "expected_output_relative_paths": expected_relative_paths,
        "files_created_or_modified": changed_paths,
        "outputs_within_workspace": all(_is_under_path(Path(path), workspace_root) for path in changed_paths),
        "protected_surface_mutation_attempted": False,
        "reference_target_context": reference_target_context,
        "quality_gap_id": str(quality_gap_blueprint.get("quality_gap_id", "")),
        "quality_dimension_id": selected_dimension_id,
        "quality_dimension_title": selected_dimension_title,
        "quality_dimension_priority_level": selected_dimension_priority_level,
        "post_run_dimension_state": str(roadmap_preview_row.get("state", "")).strip(),
        "quality_composite_state": str(
            dict(roadmap_preview.get("composite_evaluation", {})).get(
                "composite_quality_state",
                "",
            )
        ).strip(),
        "result_summary": result_summary,
    }
    improvement_payload = {
        "schema_name": SUCCESSOR_QUALITY_IMPROVEMENT_SUMMARY_SCHEMA_NAME,
        "schema_version": SUCCESSOR_QUALITY_IMPROVEMENT_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "selected_skill_pack_id": skill_pack_id,
        "selected_skill_pack_title": str(skill_pack_manifest.get("title", "")).strip(),
        "quality_gap_id": str(quality_gap_blueprint.get("quality_gap_id", "")),
        "quality_gap_title": str(quality_gap_blueprint.get("title", "")).strip(),
        "improvement_state": result_state,
        "improved_relative_to_reference_target": bool(reference_target_id),
        "reference_target_consumption_state": str(reference_target_context.get("consumption_state", "")),
        "active_bounded_reference_target_id": reference_target_id,
        "protected_live_baseline_reference_id": str(
            reference_target_context.get("protected_live_baseline_reference_id", "")
        ),
        "files_created_or_modified": changed_paths,
        "remaining_weak_areas": [] if expected_outputs_present else list(
            quality_gap_blueprint.get("weak_areas", [])
        ),
        "quality_dimension_id": selected_dimension_id,
        "quality_dimension_title": selected_dimension_title,
        "quality_dimension_priority_level": selected_dimension_priority_level,
        "pre_run_gap_state": pre_run_dimension_state,
        "post_run_dimension_state": str(roadmap_preview_row.get("state", "")).strip(),
        "quality_composite_state": str(
            dict(roadmap_preview.get("composite_evaluation", {})).get(
                "composite_quality_state",
                "",
            )
        ).strip(),
        "materially_stronger_than_reference_target_in_aggregate": bool(
            dict(roadmap_preview.get("composite_evaluation", {})).get(
                "materially_stronger_than_reference_target_in_aggregate",
                False,
            )
        ),
        "recommended_next_skill_pack_id": str(
            dict(roadmap_preview.get("next_pack_plan", {})).get(
                "selected_skill_pack_id",
                "",
            )
        ).strip(),
        "recommended_next_objective_id": str(
            dict(roadmap_preview.get("next_pack_plan", {})).get(
                "selected_objective_id",
                "",
            )
        ).strip(),
        "recommended_next_dimension_id": str(
            dict(roadmap_preview.get("next_pack_plan", {})).get(
                "selected_dimension_id",
                "",
            )
        ).strip(),
        "result_summary": str(result_payload.get("result_summary", "")),
    }
    _write_json(
        paths["skill_pack_result_path"],
        result_payload,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=skill_pack_id,
        artifact_kind="successor_skill_pack_result_json",
    )
    _write_json(
        paths["quality_improvement_summary_path"],
        improvement_payload,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=skill_pack_id,
        artifact_kind="successor_quality_improvement_summary_json",
    )
    roadmap_outputs = _materialize_successor_quality_roadmap_outputs(
        workspace_root=workspace_root,
        current_objective=current_objective,
        reference_target_context=reference_target_context,
        latest_skill_pack_invocation=invocation_payload,
        latest_skill_pack_result=result_payload,
        latest_quality_gap_summary=quality_gap_summary,
        latest_quality_improvement_summary=improvement_payload,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )
    _event(
        runtime_event_log_path,
        event_type="successor_skill_pack_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        selected_skill_pack_id=skill_pack_id,
        result_state=result_state,
        files_created_or_modified=changed_paths,
        skill_pack_result_path=str(paths["skill_pack_result_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="successor_quality_improvement_recorded",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        selected_skill_pack_id=skill_pack_id,
        quality_gap_id=str(quality_gap_blueprint.get("quality_gap_id", "")),
        improvement_state=result_state,
        quality_improvement_summary_path=str(paths["quality_improvement_summary_path"]),
    )
    return {
        "invocation": invocation_payload,
        "result": result_payload,
        "quality_gap_summary": quality_gap_summary,
        "quality_improvement_summary": improvement_payload,
        "artifact_paths": {
            "skill_pack_invocation_path": str(paths["skill_pack_invocation_path"]),
            "skill_pack_result_path": str(paths["skill_pack_result_path"]),
            "quality_gap_summary_path": str(paths["quality_gap_summary_path"]),
            "quality_improvement_summary_path": str(paths["quality_improvement_summary_path"]),
            "quality_roadmap_path": str(paths["quality_roadmap_path"]),
            "quality_priority_matrix_path": str(paths["quality_priority_matrix_path"]),
            "quality_composite_evaluation_path": str(
                paths["quality_composite_evaluation_path"]
            ),
            "quality_next_pack_plan_path": str(paths["quality_next_pack_plan_path"]),
        },
        "changed_paths": changed_paths,
        "roadmap": dict(roadmap_outputs.get("roadmap", {})),
        "priority_matrix": dict(roadmap_outputs.get("priority_matrix", {})),
        "composite_evaluation": dict(
            roadmap_outputs.get("composite_evaluation", {})
        ),
        "next_pack_plan": dict(roadmap_outputs.get("next_pack_plan", {})),
    }


def _select_planning_work_item(current_directive: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    skipped = [
        {
            "work_item_id": "protected_surface_rewrite_candidate",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        }
    ]
    admissible = sorted(
        {
            str(item).strip()
            for item in list(current_directive.get("allowed_action_classes", []))
            if str(item).strip()
        }
        & SUPPORTED_FIRST_WORK_ACTION_CLASSES
    )
    text = str(current_directive.get("directive_text", "")).strip()
    clarified = str(current_directive.get("clarified_intent_summary", "")).strip()
    if not text and not clarified:
        skipped.append(
            {
                "work_item_id": "bounded_successor_workspace_bundle",
                "reason": "directive text and clarified intent summary are missing",
            }
        )
        return None, skipped
    if not admissible:
        skipped.append(
            {
                "work_item_id": "bounded_successor_workspace_bundle",
                "reason": "no admissible first-cycle action classes are enabled",
            }
        )
        return None, skipped
    return (
        {
            "work_item_id": "bounded_successor_workspace_bundle",
            "title": "Produce a bounded successor-planning bundle inside the active workspace.",
            "selected_action_classes": admissible,
            "rationale": "start with workspace-local planning, design, and scaffold outputs only",
            "cycle_kind": "planning_only",
        },
        skipped,
    )


def _select_implementation_work_item(
    current_directive: dict[str, Any],
    *,
    baseline: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    skipped = [
        {
            "work_item_id": "protected_surface_rewrite_candidate",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        }
    ]
    admissible = sorted(
        {
            str(item).strip()
            for item in list(current_directive.get("allowed_action_classes", []))
            if str(item).strip()
        }
        & SUPPORTED_FIRST_WORK_ACTION_CLASSES
    )
    if not baseline.get("has_planning_baseline", False):
        skipped.append(
            {
                "work_item_id": "implementation_bundle_workspace_contract",
                "reason": "planning baseline artifacts are missing from the active workspace",
            }
        )
        return None, skipped
    if not admissible:
        skipped.append(
            {
                "work_item_id": "implementation_bundle_workspace_contract",
                "reason": "no admissible implementation-cycle action classes are enabled",
            }
        )
        return None, skipped
    if baseline.get("implementation_materialized", False):
        skipped.append(
            {
                "work_item_id": "implementation_bundle_workspace_contract",
                "reason": "the first implementation bundle already exists; further implementation is deferred to a later reviewed cycle",
            }
        )
        return None, skipped
    return (
        {
            "work_item_id": "implementation_bundle_workspace_contract",
            "title": "Materialize a workspace-local artifact contract and review helper bundle.",
            "selected_action_classes": admissible,
            "rationale": "build a small real code/test bundle directly from the existing planning baseline",
            "implementation_bundle_kind": "workspace_artifact_contract",
            "cycle_kind": "implementation_bearing",
        },
        skipped,
    )


def _select_continuation_planning_work_item(
    current_directive: dict[str, Any],
    *,
    planning_context: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    skipped = [
        {
            "work_item_id": "protected_surface_rewrite_candidate",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        }
    ]
    admissible = sorted(
        {
            str(item).strip()
            for item in list(current_directive.get("allowed_action_classes", []))
            if str(item).strip()
        }
        & SUPPORTED_FIRST_WORK_ACTION_CLASSES
    )
    selected_stage = dict(dict(planning_context.get("next_step", {})).get("selected_stage", {}))
    if str(selected_stage.get("stage_id", "")).strip() != "continuation_gap_analysis":
        skipped.append(
            {
                "work_item_id": "successor_continuation_gap_analysis",
                "reason": "continuation gap analysis is not the currently selected bounded next stage",
            }
        )
        return None, skipped
    if not admissible:
        skipped.append(
            {
                "work_item_id": "successor_continuation_gap_analysis",
                "reason": "no admissible continuation-planning action classes are enabled",
            }
        )
        return None, skipped
    return (
        {
            "work_item_id": "successor_continuation_gap_analysis",
            "title": "Produce a trusted-evidence continuation gap analysis for the bounded successor workspace.",
            "selected_action_classes": admissible,
            "rationale": str(dict(planning_context.get("next_step", {})).get("reason", "")),
            "cycle_kind": "planning_only",
        },
        skipped,
    )


def _select_readiness_implementation_work_item(
    current_directive: dict[str, Any],
    *,
    planning_context: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    skipped = [
        {
            "work_item_id": "protected_surface_rewrite_candidate",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        }
    ]
    admissible = sorted(
        {
            str(item).strip()
            for item in list(current_directive.get("allowed_action_classes", []))
            if str(item).strip()
        }
        & SUPPORTED_FIRST_WORK_ACTION_CLASSES
    )
    selected_stage = dict(dict(planning_context.get("next_step", {})).get("selected_stage", {}))
    if str(selected_stage.get("stage_id", "")).strip() != "successor_readiness_bundle":
        skipped.append(
            {
                "work_item_id": "successor_readiness_bundle",
                "reason": "successor readiness bundle is not the currently selected bounded next stage",
            }
        )
        return None, skipped
    if not admissible:
        skipped.append(
            {
                "work_item_id": "successor_readiness_bundle",
                "reason": "no admissible readiness-implementation action classes are enabled",
            }
        )
        return None, skipped
    return (
        {
            "work_item_id": "successor_readiness_bundle",
            "title": "Materialize a bounded successor readiness bundle inside the active workspace.",
            "selected_action_classes": admissible,
            "rationale": str(dict(planning_context.get("next_step", {})).get("reason", "")),
            "implementation_bundle_kind": "successor_package_readiness_bundle",
            "cycle_kind": "implementation_bearing",
        },
        skipped,
    )


def _finalize_session_artifacts(
    *,
    payload: dict[str, Any],
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    brief_lines: list[str],
) -> None:
    session_text = _dump(payload)
    session_artifact_path.write_text(session_text, encoding="utf-8")
    session_archive_path.write_text(session_text, encoding="utf-8")
    brief_path.write_text("\n".join(brief_lines).strip() + "\n", encoding="utf-8")


def _complete_no_admissible_work(
    *,
    payload: dict[str, Any],
    workspace_root: Path,
    plans_root: Path,
    summary_path: Path,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    skipped: list[dict[str, str]],
    reason: str,
    include_implementation_deferred_event: bool = False,
) -> dict[str, Any]:
    explanation_path = plans_root / "no_admissible_bounded_work.md"
    _write_text(
        explanation_path,
        "# No Admissible Bounded Work\n\n- " + "\n- ".join(item["reason"] for item in skipped) + "\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id="no_admissible_bounded_work",
        artifact_kind="no_work_explanation_markdown",
    )
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "no_admissible_bounded_work",
        "cycle_kind": "no_admissible_bounded_work",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "reason": reason,
        "selected_work_item": {},
        "skipped_work_items": skipped,
        "output_artifact_paths": [str(explanation_path), str(summary_path)],
        "newly_created_paths": [str(explanation_path)],
        "deferred_items": skipped,
        "next_recommended_cycle": "operator_review_required",
    }
    _write_json(
        summary_path,
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id="no_admissible_bounded_work",
        artifact_kind="bounded_work_summary_json",
    )
    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "no_admissible_bounded_work",
            "reason": reason,
            "work_cycle": {
                "work_item_id": "no_admissible_bounded_work",
                "cycle_kind": "no_admissible_bounded_work",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "summary_artifact_path": str(summary_path),
                "output_artifact_paths": list(work_summary["output_artifact_paths"]),
                "newly_created_paths": [str(explanation_path)],
                "skipped_work_items": skipped,
                "next_recommended_cycle": "operator_review_required",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            "Status: no_admissible_bounded_work",
            f"Reason: {reason}",
            f"Explanation: {explanation_path}",
        ],
    )
    if include_implementation_deferred_event:
        _event(
            runtime_event_log_path,
            event_type="implementation_bundle_deferred",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            reason=reason,
            explanation_path=str(explanation_path),
        )
    _event(
        runtime_event_log_path,
        event_type="no_admissible_bounded_work",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        explanation_path=str(explanation_path),
        summary_artifact_path=str(summary_path),
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="no_admissible_bounded_work",
        output_artifact_paths=list(work_summary["output_artifact_paths"]),
    )
    return payload


def _run_planning_cycle(
    *,
    payload: dict[str, Any],
    current_directive: dict[str, Any],
    workspace_root: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
) -> dict[str, Any]:
    paths = _workspace_paths(workspace_root)
    selected, skipped = _select_planning_work_item(current_directive)
    for item in skipped:
        _event(
            runtime_event_log_path,
            event_type="work_item_skipped",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=str(item.get("work_item_id", "")),
            reason=str(item.get("reason", "")),
        )

    if not selected:
        return _complete_no_admissible_work(
            payload=payload,
            workspace_root=workspace_root,
            plans_root=paths["plans_root"],
            summary_path=paths["summary_path"],
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            skipped=skipped,
            reason="no admissible bounded first work item was available under the current directive and action-class constraints",
        )

    _event(
        runtime_event_log_path,
        event_type="work_item_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        title=str(selected.get("title", "")),
        rationale=str(selected.get("rationale", "")),
        selected_action_classes=list(selected.get("selected_action_classes", [])),
    )
    directive_text = str(current_directive.get("directive_text", "")).strip()
    clarified = str(current_directive.get("clarified_intent_summary", "")).strip()
    constraints = [str(item) for item in list(current_directive.get("constraints", []))]
    trusted_sources = [str(item) for item in list(current_directive.get("trusted_sources", []))]
    success_criteria = [str(item) for item in list(current_directive.get("success_criteria", []))]
    deferred_items = [
        {
            "item": "workspace_local_implementation_bundle",
            "reason": "this first cycle is intentionally planning-only so the next cycle can implement from an explicit baseline",
        },
        {
            "item": "protected_surface_mutation",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        },
    ]

    _write_text(
        paths["plan_path"],
        "\n".join(
            [
                "# Bounded Work Cycle Plan",
                "",
                f"Directive ID: `{directive_id}`",
                f"Workspace: `{workspace_id} -> {workspace_root}`",
                "",
                directive_text or clarified,
                "",
                "Writable roots:",
                *[f"- `{item}`" for item in list(payload.get("allowed_write_roots", []))],
                "",
                "Protected roots:",
                *[f"- `{item}`" for item in list(payload.get("protected_root_hints", []))],
                "",
                "Selected outputs:",
                "- `plans/bounded_work_cycle_plan.md`",
                "- `docs/mutable_shell_successor_design_note.md`",
                "- `src/README.md`",
                "- `tests/README.md`",
                "- `artifacts/bounded_work_file_plan.json`",
                "- `artifacts/bounded_work_summary_latest.json`",
                "",
            ]
        )
        + "\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="work_plan_markdown",
    )
    _write_text(
        paths["design_path"],
        "\n".join(
            [
                "# Mutable-Shell Successor Design Note",
                "",
                clarified or directive_text,
                "",
                "Binding constraints:",
                *[f"- {item}" for item in constraints],
                "",
                "Trusted sources in scope:",
                *[f"- `{item}`" for item in trusted_sources],
                "",
                "Success criteria carried forward:",
                *[f"- {item}" for item in success_criteria],
                "",
            ]
        )
        + "\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="design_note_markdown",
    )
    _write_text(
        paths["src_readme_path"],
        "# Workspace Source Scaffold\n\nThis area is reserved for bounded mutable-shell implementation work only.\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="src_scaffold_readme",
    )
    _write_text(
        paths["tests_readme_path"],
        "# Workspace Test Scaffold\n\nThis area is reserved for bounded workspace-local regression coverage only.\n",
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="tests_scaffold_readme",
    )
    file_plan = {
        "schema_name": FILE_PLAN_SCHEMA_NAME,
        "schema_version": FILE_PLAN_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "planned_files": [
            {
                "relative_path": "src/successor_shell/__init__.py",
                "purpose": "workspace-local package export for successor shell helpers",
                "status": "proposed_not_created",
            },
            {
                "relative_path": "src/successor_shell/workspace_contract.py",
                "purpose": "workspace-local artifact index and review helper",
                "status": "proposed_not_created",
            },
            {
                "relative_path": "tests/test_workspace_contract.py",
                "purpose": "workspace-local regression coverage for the artifact contract helper",
                "status": "proposed_not_created",
            },
            {
                "relative_path": "docs/successor_shell_iteration_notes.md",
                "purpose": "implementation-bearing cycle note and deferred-item summary",
                "status": "proposed_not_created",
            },
        ],
        "protected_surfaces_excluded_by_default": [
            "main.py",
            "theory/nined_core.py",
            "routing logic",
            "thresholds",
            "live policy",
            "benchmark semantics",
        ],
    }
    _write_json(
        paths["file_plan_path"],
        file_plan,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="file_plan_json",
    )

    output_paths = [
        str(paths["plan_path"]),
        str(paths["design_path"]),
        str(paths["src_readme_path"]),
        str(paths["tests_readme_path"]),
        str(paths["file_plan_path"]),
        str(paths["trusted_planning_evidence_path"]),
        str(paths["missing_deliverables_path"]),
        str(paths["next_step_derivation_path"]),
        str(paths["completion_evaluation_path"]),
        str(paths["summary_path"]),
    ]
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "work_completed",
        "cycle_kind": "planning_only",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "reason": "completed one bounded successor-planning work cycle inside the active workspace",
        "selected_work_item": selected,
        "skipped_work_items": skipped,
        "output_artifact_paths": output_paths,
        "newly_created_paths": [
            str(paths["plan_path"]),
            str(paths["design_path"]),
            str(paths["src_readme_path"]),
            str(paths["tests_readme_path"]),
            str(paths["file_plan_path"]),
        ],
        "deferred_items": deferred_items,
        "next_recommended_cycle": "materialize_workspace_local_implementation",
    }
    _write_json(
        paths["summary_path"],
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="bounded_work_summary_json",
    )
    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "work_completed",
            "reason": work_summary["reason"],
            "work_cycle": {
                "work_item_id": str(selected.get("work_item_id", "")),
                "title": str(selected.get("title", "")),
                "cycle_kind": "planning_only",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "summary_artifact_path": str(paths["summary_path"]),
                "output_artifact_paths": output_paths,
                "newly_created_paths": work_summary["newly_created_paths"],
                "skipped_work_items": skipped,
                "next_recommended_cycle": "materialize_workspace_local_implementation",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            f"Status: {payload['status']}",
            f"Directive ID: `{directive_id}`",
            f"Workspace: `{workspace_id} -> {workspace_root}`",
            "",
            "Outputs:",
            *[f"- `{item}`" for item in output_paths],
        ],
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="work_completed",
        cycle_kind="planning_only",
        work_item_id=str(selected.get("work_item_id", "")),
        output_artifact_paths=output_paths,
        summary_artifact_path=str(paths["summary_path"]),
    )
    return payload


def _run_implementation_cycle(
    *,
    payload: dict[str, Any],
    current_directive: dict[str, Any],
    session: dict[str, Any],
    workspace_root: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    cycle_index: int,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
) -> dict[str, Any]:
    baseline = _workspace_baseline(workspace_root)
    _event(
        runtime_event_log_path,
        event_type="implementation_planning_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        baseline_artifact_paths=list(baseline.get("baseline_artifact_paths", [])),
    )
    selected, skipped = _select_implementation_work_item(current_directive, baseline=baseline)
    for item in skipped:
        _event(
            runtime_event_log_path,
            event_type="work_item_skipped",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=str(item.get("work_item_id", "")),
            reason=str(item.get("reason", "")),
        )

    if not selected:
        return _complete_no_admissible_work(
            payload=payload,
            workspace_root=workspace_root,
            plans_root=baseline["plans_root"],
            summary_path=baseline["summary_path"],
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            skipped=skipped,
            reason="no admissible implementation-bearing work item was available under the current directive, baseline, and action-class constraints",
            include_implementation_deferred_event=True,
        )

    _event(
        runtime_event_log_path,
        event_type="implementation_item_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        title=str(selected.get("title", "")),
        rationale=str(selected.get("rationale", "")),
        implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
        baseline_artifact_paths=list(baseline.get("baseline_artifact_paths", [])),
    )

    baseline["implementation_package_root"].mkdir(parents=True, exist_ok=True)
    deferred_items = [
        {
            "item": "protected_surface_mutation",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        },
        {
            "item": "live_trusted_source_network_queries",
            "reason": "trusted-source live network expansion remains deferred in this cycle",
        },
        {
            "item": "repo_wide_mutation",
            "reason": "this bundle remains bounded to the active workspace and generated/log roots only",
        },
    ]

    _write_text(
        baseline["implementation_init_path"],
        _implementation_init_source(),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_package_init",
    )
    _write_text(
        baseline["implementation_module_path"],
        _implementation_module_source(directive_id=directive_id),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_module_python",
    )
    _write_text(
        baseline["implementation_test_path"],
        _implementation_test_source(),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_test_python",
    )
    _event(
        runtime_event_log_path,
        event_type="test_scaffold_created",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        path=str(baseline["implementation_test_path"]),
        work_item_id=str(selected.get("work_item_id", "")),
    )
    _write_text(
        baseline["implementation_note_path"],
        _implementation_note_text(
            directive_id=directive_id,
            workspace_id=workspace_id,
            implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
            deferred_items=deferred_items,
        ),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_iteration_note_markdown",
    )

    file_plan = load_json(baseline["file_plan_path"])
    planned_files = list(file_plan.get("planned_files", []))
    updated_file_statuses = {
        "src/successor_shell/__init__.py": "created",
        "src/successor_shell/workspace_contract.py": "created",
        "tests/test_workspace_contract.py": "created",
        "docs/successor_shell_iteration_notes.md": "created",
    }
    if not planned_files:
        planned_files = [
            {
                "relative_path": relative_path,
                "purpose": "materialized during the first implementation-bearing workspace cycle",
                "status": status,
            }
            for relative_path, status in updated_file_statuses.items()
        ]
    else:
        seen_paths: set[str] = set()
        for item in planned_files:
            relative_path = str(item.get("relative_path", "")).strip()
            if not relative_path:
                continue
            seen_paths.add(relative_path)
            if relative_path in updated_file_statuses:
                item["status"] = updated_file_statuses[relative_path]
        for relative_path, status in updated_file_statuses.items():
            if relative_path in seen_paths:
                continue
            planned_files.append(
                {
                    "relative_path": relative_path,
                    "purpose": "materialized during the first implementation-bearing workspace cycle",
                    "status": status,
                }
            )
    file_plan["schema_name"] = FILE_PLAN_SCHEMA_NAME
    file_plan["schema_version"] = FILE_PLAN_SCHEMA_VERSION
    file_plan["generated_at"] = _now()
    file_plan["directive_id"] = directive_id
    file_plan["workspace_id"] = workspace_id
    file_plan["planned_files"] = planned_files
    file_plan["protected_surfaces_excluded_by_default"] = file_plan.get(
        "protected_surfaces_excluded_by_default",
        [
            "main.py",
            "theory/nined_core.py",
            "routing logic",
            "thresholds",
            "live policy",
            "benchmark semantics",
        ],
    )
    _write_json(
        baseline["file_plan_path"],
        file_plan,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="file_plan_json",
    )

    workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    _write_json(
        baseline["workspace_artifact_index_path"],
        workspace_artifact_index,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="workspace_artifact_index_json",
    )
    skill_pack_outputs = _invoke_successor_skill_pack(
        selection=_select_successor_skill_pack(
            current_directive=current_directive,
            workspace_root=workspace_root,
            session=session,
            cycle_kind="implementation_bearing",
            stage_id="first_implementation_bundle",
        ),
        workspace_root=workspace_root,
        paths=baseline,
        payload=payload,
        cycle_index=int(cycle_index),
        cycle_kind="implementation_bearing",
        stage_id="first_implementation_bundle",
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )

    created_files = [
        str(baseline["implementation_init_path"]),
        str(baseline["implementation_module_path"]),
        str(baseline["implementation_test_path"]),
        str(baseline["implementation_note_path"]),
        str(baseline["workspace_artifact_index_path"]),
    ]
    created_files.extend(list(skill_pack_outputs.get("changed_paths", [])))
    implementation_summary = {
        "schema_name": IMPLEMENTATION_BUNDLE_SCHEMA_NAME,
        "schema_version": IMPLEMENTATION_BUNDLE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "cycle_kind": "implementation_bearing",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
        "baseline_artifact_paths": list(baseline.get("baseline_artifact_paths", [])),
        "created_files": created_files,
        "deferred_items": deferred_items,
        "next_recommended_cycle": "plan_successor_package_gap_closure",
        "implementation_summary": (
            "Materialized a workspace-local artifact contract helper, executable test module, "
            "iteration note, and artifact index summary without touching protected repo surfaces."
        ),
        "skill_pack_invocation": dict(skill_pack_outputs.get("invocation", {})),
        "skill_pack_result": dict(skill_pack_outputs.get("result", {})),
        "quality_improvement_summary": dict(
            skill_pack_outputs.get("quality_improvement_summary", {})
        ),
    }
    _write_json(
        baseline["implementation_summary_path"],
        implementation_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_bundle_summary_json",
    )
    created_files.append(str(baseline["implementation_summary_path"]))

    output_paths = [
        str(baseline["implementation_init_path"]),
        str(baseline["implementation_module_path"]),
        str(baseline["implementation_test_path"]),
        str(baseline["implementation_note_path"]),
        str(baseline["file_plan_path"]),
        str(baseline["workspace_artifact_index_path"]),
        str(baseline["trusted_planning_evidence_path"]),
        str(baseline["missing_deliverables_path"]),
        str(baseline["next_step_derivation_path"]),
        str(baseline["completion_evaluation_path"]),
        str(baseline["implementation_summary_path"]),
        str(baseline["summary_path"]),
    ]
    output_paths.extend(
        [
            str(path)
            for path in (
                skill_pack_outputs.get("artifact_paths", {}) or {}
            ).values()
            if str(path).strip()
        ]
    )
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "work_completed",
        "cycle_kind": "implementation_bearing",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
        "reason": "completed one bounded implementation-bearing workspace cycle inside the active workspace",
        "selected_work_item": selected,
        "skipped_work_items": skipped,
        "baseline_artifact_paths": list(baseline.get("baseline_artifact_paths", [])),
        "output_artifact_paths": output_paths,
        "newly_created_paths": created_files,
        "deferred_items": deferred_items,
        "next_recommended_cycle": "plan_successor_package_gap_closure",
        "selected_skill_pack": dict(skill_pack_outputs.get("invocation", {})),
        "skill_pack_result": dict(skill_pack_outputs.get("result", {})),
        "quality_improvement_summary": dict(
            skill_pack_outputs.get("quality_improvement_summary", {})
        ),
    }
    _write_json(
        baseline["summary_path"],
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="bounded_work_summary_json",
    )

    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "work_completed",
            "reason": work_summary["reason"],
            "work_cycle": {
                "work_item_id": str(selected.get("work_item_id", "")),
                "title": str(selected.get("title", "")),
                "cycle_kind": "implementation_bearing",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
                "summary_artifact_path": str(baseline["summary_path"]),
                "output_artifact_paths": output_paths,
                "newly_created_paths": created_files,
                "skipped_work_items": skipped,
                "deferred_items": deferred_items,
                "next_recommended_cycle": "plan_successor_package_gap_closure",
                "selected_skill_pack": dict(skill_pack_outputs.get("invocation", {})),
                "skill_pack_result": dict(skill_pack_outputs.get("result", {})),
                "quality_improvement_summary": dict(
                    skill_pack_outputs.get("quality_improvement_summary", {})
                ),
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            f"Status: {payload['status']}",
            f"Directive ID: `{directive_id}`",
            f"Workspace: `{workspace_id} -> {workspace_root}`",
            "Cycle kind: implementation_bearing",
            f"Implementation bundle: `{selected.get('implementation_bundle_kind', '')}`",
            "",
            "Outputs:",
            *[f"- `{item}`" for item in output_paths],
        ],
    )
    _event(
        runtime_event_log_path,
        event_type="implementation_bundle_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
        created_files=created_files,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="work_completed",
        cycle_kind="implementation_bearing",
        work_item_id=str(selected.get("work_item_id", "")),
        output_artifact_paths=output_paths,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    return payload


def _run_continuation_planning_cycle(
    *,
    payload: dict[str, Any],
    current_directive: dict[str, Any],
    workspace_root: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    planning_context: dict[str, Any],
) -> dict[str, Any]:
    baseline = _workspace_baseline(workspace_root)
    selected, skipped = _select_continuation_planning_work_item(
        current_directive,
        planning_context=planning_context,
    )
    for item in skipped:
        _event(
            runtime_event_log_path,
            event_type="work_item_skipped",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=str(item.get("work_item_id", "")),
            reason=str(item.get("reason", "")),
        )

    if not selected:
        return _complete_no_admissible_work(
            payload=payload,
            workspace_root=workspace_root,
            plans_root=baseline["plans_root"],
            summary_path=baseline["summary_path"],
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            skipped=skipped,
            reason="no admissible continuation-planning work item was available under the current directive, workspace state, and trusted planning evidence",
        )

    _event(
        runtime_event_log_path,
        event_type="work_item_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        title=str(selected.get("title", "")),
        rationale=str(selected.get("rationale", "")),
        selected_action_classes=list(selected.get("selected_action_classes", [])),
    )

    missing_deliverables = list(dict(planning_context.get("missing_deliverables", {})).get("missing_required_deliverables", []))
    next_step = dict(planning_context.get("next_step", {}))
    deferred_items = [
        {
            "item": "successor_readiness_bundle",
            "reason": "the trusted planning evidence indicates a further implementation-bearing readiness bundle is still required",
        },
        {
            "item": "protected_surface_mutation",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        },
    ]

    _write_text(
        baseline["continuation_gap_plan_path"],
        _continuation_gap_analysis_text(
            directive_id=directive_id,
            workspace_id=workspace_id,
            missing_deliverables=missing_deliverables,
            next_step=next_step,
        ),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="continuation_gap_analysis_markdown",
    )

    file_plan = load_json(baseline["file_plan_path"])
    planned_files = list(file_plan.get("planned_files", []))
    planned_lookup = {
        str(item.get("relative_path", "")).strip(): item
        for item in planned_files
        if str(item.get("relative_path", "")).strip()
    }
    for relative_path, purpose in (
        ("src/successor_shell/successor_manifest.py", "workspace-local readiness and successor delivery manifest helper"),
        ("tests/test_successor_manifest.py", "workspace-local regression coverage for the successor readiness helper"),
        ("docs/successor_package_readiness_note.md", "readiness bundle note summarizing successor package scope and remaining deferments"),
        ("artifacts/successor_readiness_evaluation_latest.json", "structured readiness evaluation for the bounded successor package"),
        ("artifacts/successor_delivery_manifest_latest.json", "structured successor delivery manifest for operator review"),
    ):
        if relative_path in planned_lookup:
            planned_lookup[relative_path]["status"] = "proposed_not_created"
            continue
        planned_files.append(
            {
                "relative_path": relative_path,
                "purpose": purpose,
                "status": "proposed_not_created",
            }
        )
    file_plan["generated_at"] = _now()
    file_plan["planned_files"] = planned_files
    _write_json(
        baseline["file_plan_path"],
        file_plan,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="file_plan_json",
    )

    workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    _write_json(
        baseline["workspace_artifact_index_path"],
        workspace_artifact_index,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="workspace_artifact_index_json",
    )

    created_files = [str(baseline["continuation_gap_plan_path"])]
    output_paths = [
        str(baseline["continuation_gap_plan_path"]),
        str(baseline["trusted_planning_evidence_path"]),
        str(baseline["missing_deliverables_path"]),
        str(baseline["next_step_derivation_path"]),
        str(baseline["completion_evaluation_path"]),
        str(baseline["workspace_artifact_index_path"]),
        str(baseline["summary_path"]),
    ]
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "work_completed",
        "cycle_kind": "planning_only",
        "planning_bundle_kind": "successor_continuation_gap_analysis",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "reason": "completed one trusted-evidence continuation planning cycle inside the active workspace",
        "selected_work_item": selected,
        "skipped_work_items": skipped,
        "output_artifact_paths": output_paths,
        "newly_created_paths": created_files,
        "deferred_items": deferred_items,
        "next_recommended_cycle": "materialize_successor_package_readiness_bundle",
    }
    _write_json(
        baseline["summary_path"],
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="bounded_work_summary_json",
    )
    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "work_completed",
            "reason": work_summary["reason"],
            "work_cycle": {
                "work_item_id": str(selected.get("work_item_id", "")),
                "title": str(selected.get("title", "")),
                "cycle_kind": "planning_only",
                "planning_bundle_kind": "successor_continuation_gap_analysis",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "summary_artifact_path": str(baseline["summary_path"]),
                "output_artifact_paths": output_paths,
                "newly_created_paths": created_files,
                "skipped_work_items": skipped,
                "deferred_items": deferred_items,
                "next_recommended_cycle": "materialize_successor_package_readiness_bundle",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            f"Status: {payload['status']}",
            f"Directive ID: `{directive_id}`",
            f"Workspace: `{workspace_id} -> {workspace_root}`",
            "Cycle kind: planning_only",
            "Planning bundle: successor_continuation_gap_analysis",
            "",
            "Outputs:",
            *[f"- `{item}`" for item in output_paths],
        ],
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="work_completed",
        cycle_kind="planning_only",
        work_item_id=str(selected.get("work_item_id", "")),
        output_artifact_paths=output_paths,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    return payload


def _run_readiness_implementation_cycle(
    *,
    payload: dict[str, Any],
    current_directive: dict[str, Any],
    session: dict[str, Any],
    workspace_root: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    cycle_index: int,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    planning_context: dict[str, Any],
) -> dict[str, Any]:
    baseline = _workspace_baseline(workspace_root)
    _event(
        runtime_event_log_path,
        event_type="implementation_planning_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        baseline_artifact_paths=list(baseline.get("baseline_artifact_paths", [])),
    )
    selected, skipped = _select_readiness_implementation_work_item(
        current_directive,
        planning_context=planning_context,
    )
    for item in skipped:
        _event(
            runtime_event_log_path,
            event_type="work_item_skipped",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id=str(item.get("work_item_id", "")),
            reason=str(item.get("reason", "")),
        )

    if not selected:
        return _complete_no_admissible_work(
            payload=payload,
            workspace_root=workspace_root,
            plans_root=baseline["plans_root"],
            summary_path=baseline["summary_path"],
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            skipped=skipped,
            reason="no admissible readiness implementation bundle was available under the current directive, workspace state, and trusted planning evidence",
            include_implementation_deferred_event=True,
        )

    _event(
        runtime_event_log_path,
        event_type="implementation_item_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        title=str(selected.get("title", "")),
        rationale=str(selected.get("rationale", "")),
        implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
        baseline_artifact_paths=list(baseline.get("baseline_artifact_paths", [])),
    )

    deferred_items = [
        {
            "item": "protected_surface_mutation",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        },
        {
            "item": "live_trusted_source_network_queries",
            "reason": "trusted-source live network expansion remains deferred in this cycle",
        },
        {
            "item": "repo_wide_mutation",
            "reason": "this bundle remains bounded to the active workspace and generated/log roots only",
        },
    ]

    _write_text(
        baseline["implementation_init_path"],
        _implementation_init_source(include_readiness_helpers=True),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="implementation_package_init",
    )
    _write_text(
        baseline["readiness_module_path"],
        _successor_manifest_source(),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_manifest_python",
    )
    _write_text(
        baseline["readiness_test_path"],
        _successor_manifest_test_source(),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_manifest_test_python",
    )
    _event(
        runtime_event_log_path,
        event_type="test_scaffold_created",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        path=str(baseline["readiness_test_path"]),
        work_item_id=str(selected.get("work_item_id", "")),
    )
    _write_text(
        baseline["readiness_note_path"],
        _readiness_note_text(
            directive_id=directive_id,
            workspace_id=workspace_id,
            deferred_items=deferred_items,
        ),
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_readiness_note_markdown",
    )

    delivery_manifest = {
        "schema_name": SUCCESSOR_DELIVERY_MANIFEST_SCHEMA_NAME,
        "schema_version": SUCCESSOR_DELIVERY_MANIFEST_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "deliverables": [
            {
                "relative_path": relative_path,
                "absolute_path": str(workspace_root / relative_path),
                "present": bool((workspace_root / relative_path).exists()),
            }
            for relative_path in (
                "plans/bounded_work_cycle_plan.md",
                "docs/mutable_shell_successor_design_note.md",
                "src/successor_shell/workspace_contract.py",
                "tests/test_workspace_contract.py",
                "plans/successor_continuation_gap_analysis.md",
                "src/successor_shell/successor_manifest.py",
                "tests/test_successor_manifest.py",
                "docs/successor_package_readiness_note.md",
            )
        ],
    }
    delivery_manifest["completion_ready"] = all(
        bool(item.get("present", False)) for item in list(delivery_manifest.get("deliverables", []))
    )
    _write_json(
        baseline["delivery_manifest_path"],
        delivery_manifest,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_delivery_manifest_json",
    )
    readiness_evaluation = {
        "schema_name": SUCCESSOR_READINESS_EVALUATION_SCHEMA_NAME,
        "schema_version": SUCCESSOR_READINESS_EVALUATION_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "cycle_kind": "implementation_bearing",
        "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
        "completion_ready": bool(delivery_manifest.get("completion_ready", False)),
        "delivery_manifest_path": str(baseline["delivery_manifest_path"]),
        "created_files": [
            str(baseline["readiness_module_path"]),
            str(baseline["readiness_test_path"]),
            str(baseline["readiness_note_path"]),
            str(baseline["readiness_summary_path"]),
            str(baseline["delivery_manifest_path"]),
        ],
        "deferred_items": deferred_items,
        "next_recommended_cycle": "operator_review_required",
        "readiness_summary": "Materialized the bounded successor readiness bundle inside the active workspace.",
    }
    _write_json(
        baseline["readiness_summary_path"],
        readiness_evaluation,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_readiness_evaluation_json",
    )

    file_plan = load_json(baseline["file_plan_path"])
    planned_files = list(file_plan.get("planned_files", []))
    for item in planned_files:
        relative_path = str(item.get("relative_path", "")).strip()
        if relative_path in {
            "src/successor_shell/successor_manifest.py",
            "tests/test_successor_manifest.py",
            "docs/successor_package_readiness_note.md",
            "artifacts/successor_readiness_evaluation_latest.json",
            "artifacts/successor_delivery_manifest_latest.json",
        }:
            item["status"] = "created"
    file_plan["generated_at"] = _now()
    file_plan["planned_files"] = planned_files
    _write_json(
        baseline["file_plan_path"],
        file_plan,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="file_plan_json",
    )

    workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    _write_json(
        baseline["workspace_artifact_index_path"],
        workspace_artifact_index,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="workspace_artifact_index_json",
    )
    skill_pack_outputs = _invoke_successor_skill_pack(
        selection=_select_successor_skill_pack(
            current_directive=current_directive,
            workspace_root=workspace_root,
            session=session,
            cycle_kind="implementation_bearing",
            stage_id="successor_readiness_bundle",
        ),
        workspace_root=workspace_root,
        paths=baseline,
        payload=payload,
        cycle_index=int(cycle_index),
        cycle_kind="implementation_bearing",
        stage_id="successor_readiness_bundle",
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )

    created_files = [
        str(baseline["readiness_module_path"]),
        str(baseline["readiness_test_path"]),
        str(baseline["readiness_note_path"]),
        str(baseline["readiness_summary_path"]),
        str(baseline["delivery_manifest_path"]),
    ]
    created_files.extend(list(skill_pack_outputs.get("changed_paths", [])))
    output_paths = [
        str(baseline["implementation_init_path"]),
        str(baseline["readiness_module_path"]),
        str(baseline["readiness_test_path"]),
        str(baseline["readiness_note_path"]),
        str(baseline["trusted_planning_evidence_path"]),
        str(baseline["missing_deliverables_path"]),
        str(baseline["next_step_derivation_path"]),
        str(baseline["completion_evaluation_path"]),
        str(baseline["readiness_summary_path"]),
        str(baseline["delivery_manifest_path"]),
        str(baseline["file_plan_path"]),
        str(baseline["workspace_artifact_index_path"]),
        str(baseline["summary_path"]),
    ]
    output_paths.extend(
        [
            str(path)
            for path in (
                skill_pack_outputs.get("artifact_paths", {}) or {}
            ).values()
            if str(path).strip()
        ]
    )
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "work_completed",
        "cycle_kind": "implementation_bearing",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
        "reason": "completed one bounded successor readiness implementation cycle inside the active workspace",
        "selected_work_item": selected,
        "skipped_work_items": skipped,
        "output_artifact_paths": output_paths,
        "newly_created_paths": created_files,
        "deferred_items": deferred_items,
        "next_recommended_cycle": "operator_review_required",
        "selected_skill_pack": dict(skill_pack_outputs.get("invocation", {})),
        "skill_pack_result": dict(skill_pack_outputs.get("result", {})),
        "quality_improvement_summary": dict(
            skill_pack_outputs.get("quality_improvement_summary", {})
        ),
    }
    _write_json(
        baseline["summary_path"],
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="bounded_work_summary_json",
    )
    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "work_completed",
            "reason": work_summary["reason"],
            "work_cycle": {
                "work_item_id": str(selected.get("work_item_id", "")),
                "title": str(selected.get("title", "")),
                "cycle_kind": "implementation_bearing",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "implementation_bundle_kind": str(selected.get("implementation_bundle_kind", "")),
                "summary_artifact_path": str(baseline["summary_path"]),
                "output_artifact_paths": output_paths,
                "newly_created_paths": created_files,
                "skipped_work_items": skipped,
                "deferred_items": deferred_items,
                "next_recommended_cycle": "operator_review_required",
                "selected_skill_pack": dict(skill_pack_outputs.get("invocation", {})),
                "skill_pack_result": dict(skill_pack_outputs.get("result", {})),
                "quality_improvement_summary": dict(
                    skill_pack_outputs.get("quality_improvement_summary", {})
                ),
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            f"Status: {payload['status']}",
            f"Directive ID: `{directive_id}`",
            f"Workspace: `{workspace_id} -> {workspace_root}`",
            "Cycle kind: implementation_bearing",
            f"Implementation bundle: `{selected.get('implementation_bundle_kind', '')}`",
            "",
            "Outputs:",
            *[f"- `{item}`" for item in output_paths],
        ],
    )
    _event(
        runtime_event_log_path,
        event_type="implementation_bundle_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        implementation_bundle_kind=str(selected.get("implementation_bundle_kind", "")),
        created_files=created_files,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="work_completed",
        cycle_kind="implementation_bearing",
        work_item_id=str(selected.get("work_item_id", "")),
        output_artifact_paths=output_paths,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    return payload


def _run_promotion_bundle_cycle(
    *,
    payload: dict[str, Any],
    current_directive: dict[str, Any],
    workspace_root: Path,
    runtime_event_log_path: Path,
    session_id: str,
    directive_id: str,
    execution_profile: str,
    workspace_id: str,
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
) -> dict[str, Any]:
    baseline = _workspace_baseline(workspace_root)
    objective_context = _current_objective_context(
        current_directive=current_directive,
        workspace_root=workspace_root,
    )
    reference_target_context = _resolve_reference_target_consumption(
        current_directive=current_directive,
        workspace_root=workspace_root,
        current_objective=objective_context,
    )
    refresh_eligibility = _evaluate_revised_candidate_refresh_eligibility(
        workspace_root=workspace_root,
        current_objective=objective_context,
        completion_evaluation={"completed": True},
        reference_target_context=reference_target_context,
    )
    revised_candidate_refresh = bool(refresh_eligibility.get("eligible", False))
    candidate_bundle_identity = (
        str(refresh_eligibility.get("candidate_bundle_identity", "")).strip()
        if revised_candidate_refresh
        else str(objective_context.get("objective_id", "")).strip()
        or "prepare_candidate_promotion_bundle"
    )
    candidate_bundle_variant = (
        "revised_candidate" if revised_candidate_refresh else "candidate_promotion_bundle"
    )
    prior_admitted_candidate_id = str(
        refresh_eligibility.get("prior_admitted_candidate_id", "")
    ).strip()
    selected = {
        "work_item_id": "successor_candidate_promotion_bundle",
        "title": "Prepare a candidate promotion bundle for operator review.",
        "rationale": (
            "The operator approved the bounded next objective proposed by successor review."
            if not revised_candidate_refresh
            else "The operator approved a refreshed candidate promotion bundle so the materially improved successor can re-enter explicit promotion and admission review."
        ),
        "planning_bundle_kind": "candidate_promotion_bundle",
    }
    _event(
        runtime_event_log_path,
        event_type="work_item_selected",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        title=str(selected.get("title", "")),
        rationale=str(selected.get("rationale", "")),
        selected_action_classes=["diagnostic_schema_materialization"],
    )
    review_summary = load_json(baseline["review_summary_path"])
    promotion_recommendation = load_json(baseline["promotion_recommendation_path"])
    next_objective_proposal = load_json(baseline["next_objective_proposal_path"])
    delivery_manifest = load_json(baseline["delivery_manifest_path"])
    readiness_summary = load_json(baseline["readiness_summary_path"])

    note_text = dedent(
        f"""
        # Successor Promotion Bundle Note

        Objective: `{objective_context.get('objective_id', '')}`

        This bounded continuation cycle materialized a candidate promotion bundle inside the
        active workspace so an operator can inspect the completed successor package and its
        lineage without broadening permissions or bypassing review.

        Reviewed successor package:
        - Directive id: `{directive_id}`
        - Workspace id: `{workspace_id}`
        - Review status: `{review_summary.get('review_status', '')}`
        - Promotion recommendation: `{promotion_recommendation.get('promotion_recommendation_state', '')}`
        - Proposal approved from: `{baseline['next_objective_proposal_path']}`
        - Candidate bundle identity: `{candidate_bundle_identity}`
        - Candidate bundle variant: `{candidate_bundle_variant}`
        - Prior admitted candidate: `{prior_admitted_candidate_id or '<none>'}`
        - Materially stronger in aggregate: `{bool(refresh_eligibility.get('materially_stronger_in_aggregate', False))}`
        - Quality composite state: `{str(refresh_eligibility.get('quality_composite_state', '') or '<none>')}`

        This bundle remains review-oriented only. It does not promote anything automatically,
        and it does not mutate protected repo surfaces.
        """
    ).strip() + "\n"
    _write_text(
        baseline["promotion_bundle_note_path"],
        note_text,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_promotion_bundle_markdown",
    )
    promotion_bundle_payload = {
        "schema_name": SUCCESSOR_CANDIDATE_PROMOTION_BUNDLE_SCHEMA_NAME,
        "schema_version": SUCCESSOR_CANDIDATE_PROMOTION_BUNDLE_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "objective_id": str(objective_context.get("objective_id", "")),
        "objective_source_kind": str(objective_context.get("source_kind", "")),
        "candidate_bundle_identity": candidate_bundle_identity,
        "candidate_bundle_variant": candidate_bundle_variant,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "revised_candidate_refresh_eligible": revised_candidate_refresh,
        "revised_candidate_refresh_rationale": str(
            refresh_eligibility.get("rationale", "")
        ).strip(),
        "quality_composite_state": str(
            refresh_eligibility.get("quality_composite_state", "")
        ).strip(),
        "materially_stronger_than_prior_admitted_candidate_in_aggregate": bool(
            refresh_eligibility.get("materially_stronger_in_aggregate", False)
        ),
        "improved_dimension_ids": list(refresh_eligibility.get("improved_dimension_ids", [])),
        "remaining_weak_dimension_ids": list(refresh_eligibility.get("weak_dimension_ids", [])),
        "reference_target_consumption_path": str(baseline["reference_target_consumption_path"]),
        "review_summary_path": str(baseline["review_summary_path"]),
        "promotion_recommendation_path": str(baseline["promotion_recommendation_path"]),
        "next_objective_proposal_path": str(baseline["next_objective_proposal_path"]),
        "continuation_lineage_path": str(baseline["continuation_lineage_path"]),
        "delivery_manifest_path": str(baseline["delivery_manifest_path"]),
        "readiness_summary_path": str(baseline["readiness_summary_path"]),
        "quality_roadmap_path": str(baseline["quality_roadmap_path"]),
        "quality_priority_matrix_path": str(baseline["quality_priority_matrix_path"]),
        "quality_composite_evaluation_path": str(
            baseline["quality_composite_evaluation_path"]
        ),
        "quality_next_pack_plan_path": str(baseline["quality_next_pack_plan_path"]),
        "completion_ready": bool(readiness_summary.get("completion_ready", False)),
        "bundle_items": [
            str(baseline["promotion_bundle_note_path"]),
            str(baseline["promotion_bundle_manifest_path"]),
            str(baseline["review_summary_path"]),
            str(baseline["promotion_recommendation_path"]),
            str(baseline["next_objective_proposal_path"]),
            str(baseline["continuation_lineage_path"]),
        ],
        "delivery_manifest_deliverables": list(delivery_manifest.get("deliverables", [])),
        "operator_review_required": True,
        "automatic_promotion_permitted": False,
        "next_recommended_cycle": "operator_review_required",
    }
    _write_json(
        baseline["promotion_bundle_manifest_path"],
        promotion_bundle_payload,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="successor_candidate_promotion_bundle_json",
    )
    revised_candidate_outputs: dict[str, Any] = {}
    if revised_candidate_refresh:
        revised_candidate_outputs = _materialize_revised_candidate_bundle_outputs(
            workspace_root=workspace_root,
            current_objective=objective_context,
            current_promotion_bundle_payload=promotion_bundle_payload,
            reference_target_context=reference_target_context,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
        )
    workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
    _write_json(
        baseline["workspace_artifact_index_path"],
        workspace_artifact_index,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="workspace_artifact_index_json",
    )
    created_files = [
        str(baseline["promotion_bundle_note_path"]),
        str(baseline["promotion_bundle_manifest_path"]),
    ]
    created_files.extend(
        [
            str(path)
            for path in (
                revised_candidate_outputs.get("revised_candidate_bundle_path", ""),
                revised_candidate_outputs.get("revised_candidate_handoff_path", ""),
                revised_candidate_outputs.get("revised_candidate_comparison_path", ""),
                revised_candidate_outputs.get("revised_candidate_promotion_summary_path", ""),
            )
            if str(path).strip()
        ]
    )
    output_paths = [
        str(baseline["promotion_bundle_note_path"]),
        str(baseline["promotion_bundle_manifest_path"]),
        str(baseline["workspace_artifact_index_path"]),
        str(baseline["summary_path"]),
    ]
    output_paths.extend(
        [
            str(path)
            for path in (
                revised_candidate_outputs.get("revised_candidate_bundle_path", ""),
                revised_candidate_outputs.get("revised_candidate_handoff_path", ""),
                revised_candidate_outputs.get("revised_candidate_comparison_path", ""),
                revised_candidate_outputs.get("revised_candidate_promotion_summary_path", ""),
            )
            if str(path).strip()
        ]
    )
    deferred_items = [
        {
            "item": "automatic_promotion",
            "reason": "promotion remains operator-reviewed and is not executed automatically in this slice",
        },
        {
            "item": "protected_surface_mutation",
            "reason": "protected-surface and immutable-kernel mutation remain excluded by default",
        },
    ]
    work_summary = {
        "schema_name": WORK_SUMMARY_SCHEMA_NAME,
        "schema_version": WORK_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "status": "work_completed",
        "cycle_kind": "planning_only",
        "planning_bundle_kind": "candidate_promotion_bundle",
        "invocation_model": CYCLE_EXECUTION_MODEL,
        "reason": "completed one bounded promotion-bundle cycle inside the active workspace",
        "selected_work_item": selected,
        "skipped_work_items": [],
        "output_artifact_paths": output_paths,
        "newly_created_paths": created_files,
        "deferred_items": deferred_items,
        "candidate_bundle_identity": candidate_bundle_identity,
        "candidate_bundle_variant": candidate_bundle_variant,
        "prior_admitted_candidate_id": prior_admitted_candidate_id,
        "revised_candidate_outputs": dict(revised_candidate_outputs),
        "next_recommended_cycle": "operator_review_required",
    }
    _write_json(
        baseline["summary_path"],
        work_summary,
        log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        work_item_id=str(selected.get("work_item_id", "")),
        artifact_kind="bounded_work_summary_json",
    )
    payload.update(
        {
            "generated_at": _now(),
            "directive_id": directive_id,
            "status": "work_completed",
            "reason": work_summary["reason"],
            "work_cycle": {
                "work_item_id": str(selected.get("work_item_id", "")),
                "title": str(selected.get("title", "")),
                "cycle_kind": "planning_only",
                "planning_bundle_kind": "candidate_promotion_bundle",
                "invocation_model": CYCLE_EXECUTION_MODEL,
                "summary_artifact_path": str(baseline["summary_path"]),
                "output_artifact_paths": output_paths,
                "newly_created_paths": created_files,
                "skipped_work_items": [],
                "deferred_items": deferred_items,
                "candidate_bundle_identity": candidate_bundle_identity,
                "candidate_bundle_variant": candidate_bundle_variant,
                "next_recommended_cycle": "operator_review_required",
            },
        }
    )
    _finalize_session_artifacts(
        payload=payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=[
            "# Governed Execution Brief",
            "",
            f"Status: {payload['status']}",
            f"Directive ID: `{directive_id}`",
            f"Workspace: `{workspace_id} -> {workspace_root}`",
            "Cycle kind: planning_only",
            "Planning bundle: candidate_promotion_bundle",
            "",
            "Outputs:",
            *[f"- `{item}`" for item in output_paths],
        ],
    )
    _event(
        runtime_event_log_path,
        event_type="work_loop_completed",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        status="work_completed",
        cycle_kind="planning_only",
        work_item_id=str(selected.get("work_item_id", "")),
        output_artifact_paths=output_paths,
        summary_artifact_path=str(baseline["summary_path"]),
    )
    return payload


def run_initial_bounded_workspace_work(
    *,
    bootstrap_summary: dict[str, Any],
    session: dict[str, Any],
    payload: dict[str, Any],
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    planning_context: dict[str, Any],
    cycle_index: int,
) -> dict[str, Any]:
    workspace_root = Path(str(payload.get("workspace_root", "")))
    paths = _workspace_paths(workspace_root)
    for root in (
        paths["docs_root"],
        paths["src_root"],
        paths["tests_root"],
        paths["artifacts_root"],
        paths["plans_root"],
    ):
        root.mkdir(parents=True, exist_ok=True)

    runtime_event_log_path = Path(str(payload.get("runtime_event_log_path", "")).strip())
    directive_state_path = Path(str(dict(bootstrap_summary.get("artifact_paths", {})).get("directive_state", "")).strip())
    current_directive = dict(load_json(directive_state_path).get("current_directive_state", {}))
    directive_id = str(current_directive.get("directive_id", payload.get("directive_id", ""))).strip() or str(payload.get("directive_id", ""))
    execution_profile = str(payload.get("execution_profile", "")).strip()
    workspace_id = str(payload.get("workspace_id", "")).strip()
    session_id = str(session.get("session_id", ""))

    _event(
        runtime_event_log_path,
        event_type="governed_execution_planning_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        cycle_index=int(cycle_index),
        directive_state_path=str(directive_state_path),
    )

    stage_id = str(dict(dict(planning_context.get("next_step", {})).get("selected_stage", {})).get("stage_id", "")).strip()
    if stage_id == "initial_planning_bundle":
        return _run_planning_cycle(
            payload=payload,
            current_directive=current_directive,
            workspace_root=workspace_root,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
        )
    if stage_id == "first_implementation_bundle":
        return _run_implementation_cycle(
            payload=payload,
            current_directive=current_directive,
            session=session,
            workspace_root=workspace_root,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            cycle_index=int(cycle_index),
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
        )
    if stage_id == "continuation_gap_analysis":
        return _run_continuation_planning_cycle(
            payload=payload,
            current_directive=current_directive,
            workspace_root=workspace_root,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            planning_context=planning_context,
        )
    if stage_id == "successor_readiness_bundle":
        return _run_readiness_implementation_cycle(
            payload=payload,
            current_directive=current_directive,
            session=session,
            workspace_root=workspace_root,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            cycle_index=int(cycle_index),
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            planning_context=planning_context,
        )
    if stage_id == "candidate_promotion_bundle":
        return _run_promotion_bundle_cycle(
            payload=payload,
            current_directive=current_directive,
            workspace_root=workspace_root,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
        )
    return _complete_no_admissible_work(
        payload=payload,
        workspace_root=workspace_root,
        plans_root=paths["plans_root"],
        summary_path=paths["summary_path"],
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        skipped=[
            {
                "work_item_id": "governed_execution_stage_selection",
                "reason": str(dict(planning_context.get("next_step", {})).get("reason", "")).strip()
                or "no admissible stage was selected from the trusted planning evidence",
            }
        ],
        reason="no admissible bounded work stage was selected from trusted planning evidence",
    )


def run_governed_workspace_work_controller(
    *,
    bootstrap_summary: dict[str, Any],
    session: dict[str, Any],
    payload: dict[str, Any],
    session_artifact_path: Path,
    session_archive_path: Path,
    brief_path: Path,
    controller_mode: str,
    max_cycles_per_invocation: int,
) -> dict[str, Any]:
    workspace_root = Path(str(payload.get("workspace_root", "")))
    paths = _workspace_paths(workspace_root)
    for root in (
        paths["docs_root"],
        paths["src_root"],
        paths["tests_root"],
        paths["artifacts_root"],
        paths["plans_root"],
        paths["cycles_root"],
    ):
        root.mkdir(parents=True, exist_ok=True)

    runtime_event_log_path = Path(str(payload.get("runtime_event_log_path", "")).strip())
    directive_state_path = Path(
        str(dict(bootstrap_summary.get("artifact_paths", {})).get("directive_state", "")).strip()
    )
    current_directive = dict(load_json(directive_state_path).get("current_directive_state", {}))
    directive_id = (
        str(current_directive.get("directive_id", payload.get("directive_id", ""))).strip()
        or str(payload.get("directive_id", ""))
    )
    execution_profile = str(payload.get("execution_profile", "")).strip()
    workspace_id = str(payload.get("workspace_id", "")).strip()
    session_id = str(session.get("session_id", ""))
    invocation_model = _invocation_model_for_mode(controller_mode)
    controller_summary_path = paths["controller_summary_path"]
    prior_controller_summary = load_json(controller_summary_path)

    _event(
        runtime_event_log_path,
        event_type="governed_execution_controller_started",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        controller_mode=str(controller_mode),
        invocation_model=invocation_model,
        max_cycles_per_invocation=int(max_cycles_per_invocation),
    )

    cycle_rows: list[dict[str, Any]] = []
    stop_reason = ""
    stop_detail = ""
    latest_summary_artifact_path = ""
    latest_cycle_summary_archive_path = ""
    latest_completion_evaluation: dict[str, Any] = {}
    final_review_outputs: dict[str, Any] = {}
    final_reseed_outputs: dict[str, Any] = {}
    final_auto_continue_outputs: dict[str, Any] = {}
    latest_auto_continue_transition_path = ""
    latest_auto_continue_transition_state = ""
    latest_auto_continue_transition_from_objective_id = ""
    latest_auto_continue_transition_to_objective_id = ""
    latest_auto_continue_transition_cycle_index = 0
    latest_budget_staging_decision = AUTO_CONTINUE_STAGING_NOT_APPLICABLE
    latest_budget_staging_rationale = ""
    latest_budget_staging_objective_id = ""
    latest_budget_staging_objective_class = ""

    current_payload = dict(payload)
    for cycle_index in range(1, int(max_cycles_per_invocation) + 1):
        planning_context = _build_trusted_planning_context(
            current_directive=current_directive,
            workspace_root=workspace_root,
            session=session,
            cycle_index=int(cycle_index),
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            work_item_id="governed_execution_controller",
        )
        pre_cycle_completion = dict(planning_context.get("completion_evaluation", {}))
        selected_stage = dict(dict(planning_context.get("next_step", {})).get("selected_stage", {}))
        if bool(pre_cycle_completion.get("completed", False)):
            stop_reason = STOP_REASON_COMPLETED
            stop_detail = str(pre_cycle_completion.get("reason", "")).strip()
            latest_completion_evaluation = pre_cycle_completion
            latest_summary_artifact_path = str(paths["summary_path"]) if paths["summary_path"].exists() else latest_summary_artifact_path
            break
        if not selected_stage:
            stop_reason = STOP_REASON_NO_WORK
            stop_detail = str(dict(planning_context.get("next_step", {})).get("reason", "")).strip() or (
                "no admissible bounded work remains under the current directive and trusted planning evidence"
            )
            latest_completion_evaluation = pre_cycle_completion
            latest_summary_artifact_path = str(paths["summary_path"]) if paths["summary_path"].exists() else latest_summary_artifact_path
            break
        _event(
            runtime_event_log_path,
            event_type="governed_execution_cycle_started",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            cycle_index=int(cycle_index),
            controller_mode=str(controller_mode),
            invocation_model=invocation_model,
            stage_id=str(selected_stage.get("stage_id", "")),
            cycle_kind=str(selected_stage.get("cycle_kind", "")),
            next_recommended_cycle=str(dict(planning_context.get("next_step", {})).get("next_recommended_cycle", "")),
        )
        current_payload = run_initial_bounded_workspace_work(
            bootstrap_summary=bootstrap_summary,
            session=session,
            payload=current_payload,
            session_artifact_path=session_artifact_path,
            session_archive_path=session_archive_path,
            brief_path=brief_path,
            planning_context=planning_context,
            cycle_index=int(cycle_index),
        )
        work_cycle = dict(current_payload.get("work_cycle", {}))
        latest_summary_artifact_path = (
            str(work_cycle.get("summary_artifact_path", "")).strip() or str(paths["summary_path"])
        )
        latest_cycle_summary = load_json(Path(latest_summary_artifact_path))
        latest_completion_evaluation = _directive_completion_evaluation(
            current_directive=current_directive,
            workspace_root=workspace_root,
            session=session,
            latest_cycle_summary=latest_cycle_summary,
        )
        current_payload, augmented_summary, latest_cycle_summary_archive_path = _augment_cycle_payloads(
            payload=current_payload,
            workspace_root=workspace_root,
            cycle_index=int(cycle_index),
            controller_mode=controller_mode,
            latest_cycle_summary=latest_cycle_summary,
            completion_evaluation=latest_completion_evaluation,
        )

        cycle_status = str(current_payload.get("status", "")).strip()
        cycle_kind = str(dict(current_payload.get("work_cycle", {})).get("cycle_kind", "")).strip()
        cycle_row = {
            "cycle_index": int(cycle_index),
            "cycle_kind": cycle_kind,
            "status": cycle_status,
            "summary_artifact_path": latest_summary_artifact_path,
            "cycle_summary_archive_path": latest_cycle_summary_archive_path,
            "next_recommended_cycle": str(
                dict(current_payload.get("work_cycle", {})).get("next_recommended_cycle", "")
            ).strip(),
            "output_artifact_paths": list(dict(current_payload.get("work_cycle", {})).get("output_artifact_paths", [])),
            "newly_created_paths": list(dict(current_payload.get("work_cycle", {})).get("newly_created_paths", [])),
            "counts_toward_cycle_cap": True,
            "staged_compact_follow_on": False,
            "budget_staging_decision": AUTO_CONTINUE_STAGING_NOT_APPLICABLE,
            "budget_staging_rationale": "",
        }
        cycle_rows.append(cycle_row)

        _event(
            runtime_event_log_path,
            event_type="directive_stop_condition_evaluated",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            cycle_index=int(cycle_index),
            completed=bool(latest_completion_evaluation.get("completed", False)),
            reason=str(latest_completion_evaluation.get("reason", "")),
            fallback_used=bool(latest_completion_evaluation.get("fallback_used", False)),
        )
        _event(
            runtime_event_log_path,
            event_type="governed_execution_cycle_completed",
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            cycle_index=int(cycle_index),
            cycle_kind=cycle_kind,
            status=cycle_status,
            summary_artifact_path=latest_summary_artifact_path,
            cycle_summary_archive_path=latest_cycle_summary_archive_path,
        )

        if cycle_status == STOP_REASON_FAILURE:
            stop_reason = STOP_REASON_FAILURE
            stop_detail = str(current_payload.get("reason", "")).strip()
            break
        if cycle_status == STOP_REASON_NO_WORK:
            stop_reason = STOP_REASON_NO_WORK
            stop_detail = str(current_payload.get("reason", "")).strip()
            break
        if bool(latest_completion_evaluation.get("completed", False)):
            if str(controller_mode).strip() == "multi_cycle":
                current_objective = dict(
                    latest_completion_evaluation.get(
                        "current_objective",
                        _current_objective_context(
                            current_directive=current_directive,
                            workspace_root=workspace_root,
                        ),
                    )
                )
                review_outputs = _materialize_successor_review_outputs(
                    current_directive=current_directive,
                    workspace_root=workspace_root,
                    session=session,
                    stop_reason=STOP_REASON_COMPLETED,
                    stop_detail=str(latest_completion_evaluation.get("reason", "")).strip(),
                    next_recommended_cycle=str(
                        dict(current_payload.get("work_cycle", {})).get("next_recommended_cycle", "")
                    ).strip(),
                    completion_evaluation=latest_completion_evaluation,
                    cycle_rows=cycle_rows,
                    latest_summary_artifact_path=latest_summary_artifact_path,
                    runtime_event_log_path=runtime_event_log_path,
                    session_id=session_id,
                    directive_id=directive_id,
                    execution_profile=execution_profile,
                    workspace_id=workspace_id,
                )
                updated_effective_next_objective = _update_effective_next_objective_after_run(
                    workspace_root=workspace_root,
                    current_objective=current_objective,
                    completion_evaluation=latest_completion_evaluation,
                    stop_reason=STOP_REASON_COMPLETED,
                    stop_detail=str(latest_completion_evaluation.get("reason", "")).strip(),
                )
                if (
                    str(current_objective.get("source_kind", "")).strip()
                    == OBJECTIVE_SOURCE_APPROVED_RESEED
                    and not bool(latest_completion_evaluation.get("completed", False))
                ):
                    reseed_outputs = {
                        "request": load_json(paths["reseed_request_path"]),
                        "decision": load_json(paths["reseed_decision_path"]),
                        "continuation_lineage": load_json(paths["continuation_lineage_path"]),
                        "effective_next_objective": updated_effective_next_objective
                        or load_json(paths["effective_next_objective_path"]),
                        "reseed_request_path": str(paths["reseed_request_path"]),
                        "reseed_decision_path": str(paths["reseed_decision_path"]),
                        "continuation_lineage_path": str(paths["continuation_lineage_path"]),
                        "effective_next_objective_path": str(paths["effective_next_objective_path"]),
                    }
                else:
                    reseed_outputs = _materialize_successor_reseed_request_outputs(
                        current_directive=current_directive,
                        workspace_root=workspace_root,
                        review_outputs=review_outputs,
                        runtime_event_log_path=runtime_event_log_path,
                        session_id=session_id,
                        directive_id=directive_id,
                        execution_profile=execution_profile,
                        workspace_id=workspace_id,
                    )
                budget_overview = _cycle_budget_overview(
                    cycle_rows,
                    max_cycles_per_invocation=int(max_cycles_per_invocation),
                )
                remaining_counted_cycle_budget = int(
                    budget_overview.get("remaining_counted_cycle_budget", 0) or 0
                )
                proposed_objective_id = str(
                    dict(review_outputs.get("next_objective_proposal", {})).get(
                        "objective_id",
                        "",
                    )
                ).strip()
                proposed_objective_class = str(
                    dict(review_outputs.get("next_objective_proposal", {})).get(
                        "objective_class",
                        "",
                    )
                ).strip() or _objective_class_from_objective_id(proposed_objective_id)
                compact_objective_eligible = _is_compact_auto_continue_objective(
                    proposed_objective_class
                )
                allow_same_session_execution = remaining_counted_cycle_budget > 0
                preferred_staging_decision = AUTO_CONTINUE_STAGING_NOT_APPLICABLE
                preferred_staging_rationale = ""
                counts_toward_cycle_cap = True
                if proposed_objective_id:
                    if allow_same_session_execution:
                        preferred_staging_decision = AUTO_CONTINUE_STAGING_NEXT_CYCLE
                        preferred_staging_rationale = (
                            "remaining counted cycle budget of "
                            f"{remaining_counted_cycle_budget} allowed the next bounded objective "
                            f"{proposed_objective_id} to continue in the current governed invocation"
                        )
                    elif compact_objective_eligible:
                        preferred_staging_decision = (
                            AUTO_CONTINUE_STAGING_COMPACT_FOLLOW_ON
                        )
                        preferred_staging_rationale = (
                            "counted cycle budget is exhausted, but the next bounded objective "
                            f"{proposed_objective_id} is explicitly whitelisted as a compact "
                            "follow-on and all prerequisite review and reseed artifacts are already materialized"
                        )
                        counts_toward_cycle_cap = False
                    else:
                        preferred_staging_decision = (
                            AUTO_CONTINUE_STAGING_DEFERRED_CYCLE_BUDGET
                        )
                        preferred_staging_rationale = (
                            "the next bounded objective "
                            f"{proposed_objective_id} was derived and admissible, but it was reserved "
                            "for a fresh governed invocation because the counted cycle budget for this session is exhausted"
                        )
                auto_continue_outputs = _evaluate_successor_auto_continue(
                    workspace_root=workspace_root,
                    session=session,
                    execution_profile=execution_profile,
                    runtime_event_log_path=runtime_event_log_path,
                    session_id=session_id,
                    directive_id=directive_id,
                    stop_reason=STOP_REASON_COMPLETED,
                    review_outputs=review_outputs,
                    reseed_outputs=reseed_outputs,
                    allow_same_session_execution=allow_same_session_execution,
                    preferred_staging_decision=preferred_staging_decision,
                    preferred_staging_rationale=preferred_staging_rationale,
                    remaining_counted_cycle_budget=remaining_counted_cycle_budget,
                    compact_objective_eligible=compact_objective_eligible,
                    counts_toward_cycle_cap=counts_toward_cycle_cap,
                )
                reseed_outputs = dict(auto_continue_outputs.get("reseed_outputs", reseed_outputs))
                resolved_staging_decision = str(
                    auto_continue_outputs.get("staging_decision", "")
                ).strip() or preferred_staging_decision
                resolved_staging_rationale = str(
                    auto_continue_outputs.get("staging_rationale", "")
                ).strip() or preferred_staging_rationale
                if resolved_staging_decision != AUTO_CONTINUE_STAGING_NOT_APPLICABLE:
                    latest_budget_staging_decision = resolved_staging_decision
                    latest_budget_staging_rationale = resolved_staging_rationale
                    latest_budget_staging_objective_id = proposed_objective_id
                    latest_budget_staging_objective_class = proposed_objective_class
                if bool(auto_continue_outputs.get("continuation_authorized", False)) and str(
                    auto_continue_outputs.get("authorization_origin", "")
                ).strip() == AUTO_CONTINUE_ORIGIN_POLICY:
                    if allow_same_session_execution:
                        transition_outputs = _start_same_session_auto_continue(
                            workspace_root=workspace_root,
                            current_objective=current_objective,
                            review_outputs=review_outputs,
                            reseed_outputs=reseed_outputs,
                            auto_continue_outputs=auto_continue_outputs,
                            runtime_event_log_path=runtime_event_log_path,
                            session_id=session_id,
                            directive_id=directive_id,
                            execution_profile=execution_profile,
                            workspace_id=workspace_id,
                            completed_cycle_index=int(cycle_index),
                            staging_decision=preferred_staging_decision,
                            staging_rationale=preferred_staging_rationale,
                            remaining_counted_cycle_budget=remaining_counted_cycle_budget,
                            compact_objective_eligible=compact_objective_eligible,
                            counts_toward_cycle_cap=True,
                        )
                        latest_auto_continue_transition_path = str(
                            transition_outputs.get("transition_path", "")
                        )
                        latest_auto_continue_transition_state = str(
                            transition_outputs.get("transition_state", "")
                        )
                        latest_auto_continue_transition_from_objective_id = str(
                            current_objective.get("objective_id", "")
                        ).strip()
                        latest_auto_continue_transition_to_objective_id = str(
                            dict(transition_outputs.get("effective_next_objective", {})).get(
                                "objective_id",
                                "",
                            )
                        ).strip()
                        latest_auto_continue_transition_cycle_index = int(
                            transition_outputs.get("next_cycle_index", 0) or 0
                        )
                        continue
                    if compact_objective_eligible:
                        compact_follow_on_outputs = _run_compact_follow_on_same_invocation(
                            bootstrap_summary=bootstrap_summary,
                            session=session,
                            payload=current_payload,
                            workspace_root=workspace_root,
                            current_directive=current_directive,
                            session_artifact_path=session_artifact_path,
                            session_archive_path=session_archive_path,
                            brief_path=brief_path,
                            runtime_event_log_path=runtime_event_log_path,
                            session_id=session_id,
                            directive_id=directive_id,
                            execution_profile=execution_profile,
                            workspace_id=workspace_id,
                            controller_mode=controller_mode,
                            completed_cycle_index=int(cycle_index),
                            current_objective=current_objective,
                            review_outputs=review_outputs,
                            reseed_outputs=reseed_outputs,
                            auto_continue_outputs=auto_continue_outputs,
                            staging_decision=preferred_staging_decision,
                            staging_rationale=preferred_staging_rationale,
                            remaining_counted_cycle_budget=remaining_counted_cycle_budget,
                            compact_objective_eligible=compact_objective_eligible,
                        )
                        current_payload = dict(compact_follow_on_outputs.get("payload", current_payload))
                        latest_summary_artifact_path = str(
                            compact_follow_on_outputs.get("summary_artifact_path", "")
                        ).strip() or latest_summary_artifact_path
                        latest_cycle_summary_archive_path = str(
                            compact_follow_on_outputs.get("cycle_summary_archive_path", "")
                        ).strip() or latest_cycle_summary_archive_path
                        latest_completion_evaluation = dict(
                            compact_follow_on_outputs.get("completion_evaluation", {})
                        )
                        cycle_rows.append(dict(compact_follow_on_outputs.get("cycle_row", {})))
                        transition_outputs = dict(
                            compact_follow_on_outputs.get("transition_outputs", {})
                        )
                        latest_auto_continue_transition_path = str(
                            transition_outputs.get("transition_path", "")
                        )
                        latest_auto_continue_transition_state = str(
                            transition_outputs.get("transition_state", "")
                        )
                        latest_auto_continue_transition_from_objective_id = str(
                            current_objective.get("objective_id", "")
                        ).strip()
                        latest_auto_continue_transition_to_objective_id = str(
                            dict(transition_outputs.get("effective_next_objective", {})).get(
                                "objective_id",
                                "",
                            )
                        ).strip()
                        latest_auto_continue_transition_cycle_index = int(
                            transition_outputs.get("next_cycle_index", 0) or 0
                        )
                        stop_reason = str(
                            compact_follow_on_outputs.get("stop_reason", "")
                        ).strip()
                        stop_detail = str(
                            compact_follow_on_outputs.get("stop_detail", "")
                        ).strip()
                        break
                    final_review_outputs = review_outputs
                    final_reseed_outputs = reseed_outputs
                    final_auto_continue_outputs = auto_continue_outputs
                    stop_reason = STOP_REASON_MAX_CAP
                    stop_detail = (
                        "policy-bounded auto-continue authorized the next objective "
                        f"{str(dict(reseed_outputs.get('effective_next_objective', {})).get('objective_id', '')).strip() or '<unknown>'}, "
                        "but this governed execution invocation reached the operator-selected cycle cap "
                        f"of {int(max_cycles_per_invocation)} before the next bounded cycle could start"
                    )
                    break
                final_review_outputs = review_outputs
                final_reseed_outputs = reseed_outputs
                final_auto_continue_outputs = auto_continue_outputs
            stop_reason = STOP_REASON_COMPLETED
            stop_detail = str(latest_completion_evaluation.get("reason", "")).strip()
            break
        if str(controller_mode).strip() == "single_cycle":
            stop_reason = STOP_REASON_SINGLE_CYCLE
            stop_detail = "single-cycle mode stops after one bounded cycle and returns control to the operator"
            break

    if not stop_reason:
        stop_reason = STOP_REASON_MAX_CAP
        stop_detail = (
            f"bounded governed execution reached the operator-selected cycle cap of {int(max_cycles_per_invocation)}"
        )

    latest_cycle_index = int(cycle_rows[-1]["cycle_index"]) if cycle_rows else 0
    latest_cycle_kind = str(cycle_rows[-1].get("cycle_kind", "")) if cycle_rows else ""
    latest_next_recommended_cycle = (
        str(cycle_rows[-1].get("next_recommended_cycle", ""))
        if cycle_rows
        else str(load_json(paths["next_step_derivation_path"]).get("next_recommended_cycle", ""))
    )
    if not latest_summary_artifact_path and paths["summary_path"].exists():
        latest_summary_artifact_path = str(paths["summary_path"])
    review_cycle_rows = cycle_rows or list(dict(prior_controller_summary).get("cycle_rows", []))
    if not latest_cycle_index and review_cycle_rows:
        latest_cycle_index = int(review_cycle_rows[-1].get("cycle_index", 0) or 0)
    if not latest_cycle_kind and review_cycle_rows:
        latest_cycle_kind = str(review_cycle_rows[-1].get("cycle_kind", ""))
    if not latest_summary_artifact_path:
        latest_summary_artifact_path = str(
            dict(prior_controller_summary).get("latest_summary_artifact_path", "")
        ).strip()
    if not latest_completion_evaluation:
        latest_completion_evaluation = dict(
            dict(prior_controller_summary).get("directive_completion_evaluation", {})
        )
    current_objective = dict(
        latest_completion_evaluation.get(
            "current_objective",
            _current_objective_context(
                current_directive=current_directive,
                workspace_root=workspace_root,
            ),
        )
    )
    if final_review_outputs:
        review_outputs = final_review_outputs
    else:
        review_outputs = _materialize_successor_review_outputs(
            current_directive=current_directive,
            workspace_root=workspace_root,
            session=session,
            stop_reason=stop_reason,
            stop_detail=stop_detail,
            next_recommended_cycle=latest_next_recommended_cycle,
            completion_evaluation=latest_completion_evaluation,
            cycle_rows=review_cycle_rows,
            latest_summary_artifact_path=latest_summary_artifact_path,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
        )
    if final_reseed_outputs:
        reseed_outputs = final_reseed_outputs
    else:
        updated_effective_next_objective = _update_effective_next_objective_after_run(
            workspace_root=workspace_root,
            current_objective=current_objective,
            completion_evaluation=latest_completion_evaluation,
            stop_reason=stop_reason,
            stop_detail=stop_detail,
        )
        if (
            str(current_objective.get("source_kind", "")).strip() == OBJECTIVE_SOURCE_APPROVED_RESEED
            and not bool(latest_completion_evaluation.get("completed", False))
        ):
            reseed_outputs = {
                "request": load_json(paths["reseed_request_path"]),
                "decision": load_json(paths["reseed_decision_path"]),
                "continuation_lineage": load_json(paths["continuation_lineage_path"]),
                "effective_next_objective": updated_effective_next_objective
                or load_json(paths["effective_next_objective_path"]),
                "reseed_request_path": str(paths["reseed_request_path"]),
                "reseed_decision_path": str(paths["reseed_decision_path"]),
                "continuation_lineage_path": str(paths["continuation_lineage_path"]),
                "effective_next_objective_path": str(paths["effective_next_objective_path"]),
            }
        else:
            reseed_outputs = _materialize_successor_reseed_request_outputs(
                current_directive=current_directive,
                workspace_root=workspace_root,
                review_outputs=review_outputs,
                runtime_event_log_path=runtime_event_log_path,
                session_id=session_id,
                directive_id=directive_id,
                execution_profile=execution_profile,
                workspace_id=workspace_id,
            )
    if final_auto_continue_outputs:
        auto_continue_outputs = final_auto_continue_outputs
    else:
        auto_continue_outputs = _evaluate_successor_auto_continue(
            workspace_root=workspace_root,
            session=session,
            execution_profile=execution_profile,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            stop_reason=stop_reason,
            review_outputs=review_outputs,
            reseed_outputs=reseed_outputs,
            allow_same_session_execution=False,
            preferred_staging_decision=latest_budget_staging_decision,
            preferred_staging_rationale=latest_budget_staging_rationale,
            remaining_counted_cycle_budget=int(
                _cycle_budget_overview(
                    cycle_rows,
                    max_cycles_per_invocation=int(max_cycles_per_invocation),
                ).get("remaining_counted_cycle_budget", 0)
                or 0
            ),
            compact_objective_eligible=bool(
                latest_budget_staging_decision
                == AUTO_CONTINUE_STAGING_COMPACT_FOLLOW_ON
            ),
            counts_toward_cycle_cap=bool(
                latest_budget_staging_decision != AUTO_CONTINUE_STAGING_COMPACT_FOLLOW_ON
            ),
        )
        reseed_outputs = dict(auto_continue_outputs.get("reseed_outputs", reseed_outputs))
    admission_outputs = _materialize_successor_baseline_admission_outputs(
        current_directive=current_directive,
        workspace_root=workspace_root,
        session=session,
        stop_reason=stop_reason,
        stop_detail=stop_detail,
        completion_evaluation=latest_completion_evaluation,
        cycle_rows=review_cycle_rows,
        latest_summary_artifact_path=latest_summary_artifact_path,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )
    reference_target_consumption = dict(
        latest_completion_evaluation.get("working_reference_target", {})
    )
    if not reference_target_consumption:
        reference_target_consumption = load_json(
            paths["reference_target_consumption_path"]
        )
    latest_skill_pack_invocation = load_json(paths["skill_pack_invocation_path"])
    latest_skill_pack_result = load_json(paths["skill_pack_result_path"])
    latest_quality_gap_summary = load_json(paths["quality_gap_summary_path"])
    latest_quality_improvement_summary = load_json(
        paths["quality_improvement_summary_path"]
    )
    quality_roadmap_outputs = _materialize_successor_quality_roadmap_outputs(
        workspace_root=workspace_root,
        current_objective=current_objective,
        reference_target_context=reference_target_consumption,
        latest_skill_pack_invocation=latest_skill_pack_invocation,
        latest_skill_pack_result=latest_skill_pack_result,
        latest_quality_gap_summary=latest_quality_gap_summary,
        latest_quality_improvement_summary=latest_quality_improvement_summary,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )
    controller_budget_overview = _cycle_budget_overview(
        cycle_rows,
        max_cycles_per_invocation=int(max_cycles_per_invocation),
    )
    quality_chain_reentry = _materialize_successor_quality_chain_reentry(
        workspace_root=workspace_root,
        current_objective=current_objective,
        completion_evaluation=latest_completion_evaluation,
        review_outputs=review_outputs,
        reseed_outputs=reseed_outputs,
        auto_continue_outputs=auto_continue_outputs,
        stop_reason=stop_reason,
        stop_detail=stop_detail,
        remaining_counted_cycle_budget=int(
            controller_budget_overview.get("remaining_counted_cycle_budget", 0) or 0
        ),
        budget_staging_decision=latest_budget_staging_decision,
        budget_staging_rationale=latest_budget_staging_rationale,
        auto_continue_transition_state=latest_auto_continue_transition_state,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )
    revised_candidate_bundle = load_json(paths["revised_candidate_bundle_path"])
    revised_candidate_handoff = load_json(paths["revised_candidate_handoff_path"])
    revised_candidate_comparison = load_json(paths["revised_candidate_comparison_path"])
    revised_candidate_promotion_summary = load_json(
        paths["revised_candidate_promotion_summary_path"]
    )
    generation_progress_outputs = _materialize_successor_generation_progress_outputs(
        workspace_root=workspace_root,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )
    strategy_selection_outputs = _materialize_successor_strategy_selection_outputs(
        workspace_root=workspace_root,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )
    strategy_follow_on_outputs = _materialize_successor_strategy_follow_on_handoff(
        current_directive=current_directive,
        workspace_root=workspace_root,
        session=session,
        review_outputs=review_outputs,
        reseed_outputs=reseed_outputs,
        strategy_selection_outputs=strategy_selection_outputs,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )
    if bool(strategy_follow_on_outputs.get("strategy_follow_on_materialized", False)):
        review_outputs = dict(strategy_follow_on_outputs.get("review_outputs", review_outputs))
        reseed_outputs = dict(strategy_follow_on_outputs.get("reseed_outputs", reseed_outputs))
        quality_chain_reentry = _materialize_successor_quality_chain_reentry(
            workspace_root=workspace_root,
            current_objective=current_objective,
            completion_evaluation=latest_completion_evaluation,
            review_outputs=review_outputs,
            reseed_outputs=reseed_outputs,
            auto_continue_outputs=auto_continue_outputs,
            stop_reason=stop_reason,
            stop_detail=stop_detail,
            remaining_counted_cycle_budget=int(
                controller_budget_overview.get("remaining_counted_cycle_budget", 0) or 0
            ),
            budget_staging_decision=latest_budget_staging_decision,
            budget_staging_rationale=latest_budget_staging_rationale,
            auto_continue_transition_state=latest_auto_continue_transition_state,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
        )
    campaign_governance_outputs = _materialize_successor_campaign_governance_outputs(
        workspace_root=workspace_root,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )
    campaign_follow_on_outputs = _materialize_successor_campaign_follow_on_handoff(
        current_directive=current_directive,
        workspace_root=workspace_root,
        session=session,
        review_outputs=review_outputs,
        reseed_outputs=reseed_outputs,
        campaign_governance_outputs=campaign_governance_outputs,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )
    if bool(campaign_follow_on_outputs.get("campaign_follow_on_materialized", False)):
        review_outputs = dict(campaign_follow_on_outputs.get("review_outputs", review_outputs))
        reseed_outputs = dict(campaign_follow_on_outputs.get("reseed_outputs", reseed_outputs))
        quality_chain_reentry = _materialize_successor_quality_chain_reentry(
            workspace_root=workspace_root,
            current_objective=current_objective,
            completion_evaluation=latest_completion_evaluation,
            review_outputs=review_outputs,
            reseed_outputs=reseed_outputs,
            auto_continue_outputs=auto_continue_outputs,
            stop_reason=stop_reason,
            stop_detail=stop_detail,
            remaining_counted_cycle_budget=int(
                controller_budget_overview.get("remaining_counted_cycle_budget", 0) or 0
            ),
            budget_staging_decision=latest_budget_staging_decision,
            budget_staging_rationale=latest_budget_staging_rationale,
            auto_continue_transition_state=latest_auto_continue_transition_state,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
        )
    campaign_cycle_governance_outputs = (
        _materialize_successor_campaign_cycle_governance_outputs(
            workspace_root=workspace_root,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
        )
    )
    campaign_cycle_follow_on_outputs = (
        _materialize_successor_campaign_cycle_follow_on_handoff(
            current_directive=current_directive,
            workspace_root=workspace_root,
            session=session,
            review_outputs=review_outputs,
            reseed_outputs=reseed_outputs,
            campaign_cycle_governance_outputs=campaign_cycle_governance_outputs,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
        )
    )
    if bool(
        campaign_cycle_follow_on_outputs.get(
            "campaign_cycle_follow_on_materialized", False
        )
    ):
        review_outputs = dict(
            campaign_cycle_follow_on_outputs.get("review_outputs", review_outputs)
        )
        reseed_outputs = dict(
            campaign_cycle_follow_on_outputs.get("reseed_outputs", reseed_outputs)
        )
        quality_chain_reentry = _materialize_successor_quality_chain_reentry(
            workspace_root=workspace_root,
            current_objective=current_objective,
            completion_evaluation=latest_completion_evaluation,
            review_outputs=review_outputs,
            reseed_outputs=reseed_outputs,
            auto_continue_outputs=auto_continue_outputs,
            stop_reason=stop_reason,
            stop_detail=stop_detail,
            remaining_counted_cycle_budget=int(
                controller_budget_overview.get("remaining_counted_cycle_budget", 0) or 0
            ),
            budget_staging_decision=latest_budget_staging_decision,
            budget_staging_rationale=latest_budget_staging_rationale,
            auto_continue_transition_state=latest_auto_continue_transition_state,
            runtime_event_log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
        )
    loop_governance_outputs = _materialize_successor_loop_governance_outputs(
        workspace_root=workspace_root,
        runtime_event_log_path=runtime_event_log_path,
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
    )
    controller_summary = {
        "schema_name": CONTROLLER_SUMMARY_SCHEMA_NAME,
        "schema_version": CONTROLLER_SUMMARY_SCHEMA_VERSION,
        "generated_at": _now(),
        "directive_id": directive_id,
        "workspace_id": workspace_id,
        "workspace_root": str(workspace_root),
        "controller_mode": str(controller_mode),
        "invocation_model": invocation_model,
        "max_cycles_per_invocation": int(max_cycles_per_invocation),
        "cycles_completed": int(controller_budget_overview.get("counted_cycle_count", 0) or 0),
        "staged_compact_follow_on_count": int(
            controller_budget_overview.get("staged_compact_follow_on_count", 0) or 0
        ),
        "total_executed_objective_rows": int(
            controller_budget_overview.get("total_objective_rows", 0) or 0
        ),
        "remaining_counted_cycle_budget": int(
            controller_budget_overview.get("remaining_counted_cycle_budget", 0) or 0
        ),
        "latest_cycle_index": latest_cycle_index,
        "latest_cycle_kind": latest_cycle_kind,
        "latest_summary_artifact_path": latest_summary_artifact_path,
        "latest_cycle_summary_archive_path": latest_cycle_summary_archive_path,
        "latest_trusted_planning_evidence_path": str(paths["trusted_planning_evidence_path"]),
        "latest_missing_deliverables_path": str(paths["missing_deliverables_path"]),
        "latest_next_step_derivation_path": str(paths["next_step_derivation_path"]),
        "latest_completion_evaluation_path": str(paths["completion_evaluation_path"]),
        "latest_successor_review_summary_path": str(review_outputs.get("review_summary_path", "")),
        "latest_successor_promotion_recommendation_path": str(
            review_outputs.get("promotion_recommendation_path", "")
        ),
        "latest_successor_next_objective_proposal_path": str(
            review_outputs.get("next_objective_proposal_path", "")
        ),
        "latest_successor_reseed_request_path": str(reseed_outputs.get("reseed_request_path", "")),
        "latest_successor_reseed_decision_path": str(reseed_outputs.get("reseed_decision_path", "")),
        "latest_successor_continuation_lineage_path": str(
            reseed_outputs.get("continuation_lineage_path", "")
        ),
        "latest_successor_effective_next_objective_path": str(
            reseed_outputs.get("effective_next_objective_path", "")
        ),
        "latest_successor_baseline_admission_review_path": str(
            admission_outputs.get("review_path", "")
        ),
        "latest_successor_baseline_admission_recommendation_path": str(
            admission_outputs.get("recommendation_path", "")
        ),
        "latest_successor_baseline_admission_decision_path": str(
            admission_outputs.get("decision_path", "")
        ),
        "latest_successor_baseline_remediation_proposal_path": str(
            admission_outputs.get("remediation_proposal_path", "")
        ),
        "latest_successor_admitted_candidate_path": str(
            admission_outputs.get("admitted_candidate_path", "")
        ),
        "latest_successor_admitted_candidate_handoff_path": str(
            admission_outputs.get("admitted_candidate_handoff_path", "")
        ),
        "latest_successor_baseline_comparison_path": str(
            admission_outputs.get("baseline_comparison_path", "")
        ),
        "latest_successor_reference_target_path": str(
            admission_outputs.get("reference_target_path", "")
        ),
        "latest_successor_revised_candidate_bundle_path": str(
            paths["revised_candidate_bundle_path"]
        ),
        "latest_successor_revised_candidate_handoff_path": str(
            paths["revised_candidate_handoff_path"]
        ),
        "latest_successor_revised_candidate_comparison_path": str(
            paths["revised_candidate_comparison_path"]
        ),
        "latest_successor_revised_candidate_promotion_summary_path": str(
            paths["revised_candidate_promotion_summary_path"]
        ),
        "latest_successor_reference_target_consumption_path": str(
            paths["reference_target_consumption_path"]
        ),
        "latest_successor_skill_pack_invocation_path": str(
            paths["skill_pack_invocation_path"]
        ),
        "latest_successor_skill_pack_result_path": str(
            paths["skill_pack_result_path"]
        ),
        "latest_successor_quality_gap_summary_path": str(
            paths["quality_gap_summary_path"]
        ),
        "latest_successor_quality_improvement_summary_path": str(
            paths["quality_improvement_summary_path"]
        ),
        "latest_successor_quality_roadmap_path": str(paths["quality_roadmap_path"]),
        "latest_successor_quality_priority_matrix_path": str(
            paths["quality_priority_matrix_path"]
        ),
        "latest_successor_quality_composite_evaluation_path": str(
            paths["quality_composite_evaluation_path"]
        ),
        "latest_successor_quality_next_pack_plan_path": str(
            paths["quality_next_pack_plan_path"]
        ),
        "latest_successor_quality_chain_reentry_path": str(
            paths["quality_chain_reentry_path"]
        ),
        "latest_successor_generation_history_path": str(
            paths["generation_history_path"]
        ),
        "latest_successor_generation_delta_path": str(paths["generation_delta_path"]),
        "latest_successor_progress_governance_path": str(
            paths["progress_governance_path"]
        ),
        "latest_successor_progress_recommendation_path": str(
            paths["progress_recommendation_path"]
        ),
        "latest_successor_strategy_selection_path": str(
            paths["strategy_selection_path"]
        ),
        "latest_successor_strategy_rationale_path": str(
            paths["strategy_rationale_path"]
        ),
        "latest_successor_strategy_follow_on_plan_path": str(
            paths["strategy_follow_on_plan_path"]
        ),
        "latest_successor_strategy_decision_support_path": str(
            paths["strategy_decision_support_path"]
        ),
        "stop_reason": stop_reason,
        "stop_detail": stop_detail,
        "directive_completion_evaluation": latest_completion_evaluation,
        "next_recommended_cycle": latest_next_recommended_cycle,
        "current_objective_source_kind": str(current_objective.get("source_kind", "")),
        "current_objective_id": str(current_objective.get("objective_id", "")),
        "current_objective_class": str(current_objective.get("objective_class", "")),
        "current_objective_title": str(current_objective.get("title", "")),
        "review_status": str(dict(review_outputs.get("review_summary", {})).get("review_status", "")),
        "promotion_recommendation_state": str(
            dict(review_outputs.get("promotion_recommendation", {})).get("promotion_recommendation_state", "")
        ),
        "next_objective_state": str(
            dict(review_outputs.get("next_objective_proposal", {})).get("proposal_state", "")
        ),
        "next_objective_id": str(dict(review_outputs.get("next_objective_proposal", {})).get("objective_id", "")),
        "next_objective_class": str(
            dict(review_outputs.get("next_objective_proposal", {})).get("objective_class", "")
        ),
        "operator_review_required": bool(
            dict(review_outputs.get("review_summary", {})).get("operator_review_required", False)
        ),
        "baseline_admission_review_state": str(
            dict(admission_outputs.get("review", {})).get("admission_review_state", "")
        ),
        "baseline_admission_recommendation_state": str(
            dict(admission_outputs.get("recommendation", {})).get(
                "admission_recommendation_state",
                "",
            )
        ),
        "baseline_admission_decision_state": str(
            dict(admission_outputs.get("decision", {})).get("admission_decision_state", "")
        ),
        "baseline_candidate_admitted": bool(
            dict(admission_outputs.get("decision", {})).get(
                "admitted_bounded_baseline_candidate",
                False,
            )
        ),
        "baseline_remediation_objective_id": str(
            dict(admission_outputs.get("remediation_proposal", {})).get("objective_id", "")
        ),
        "admitted_candidate_state": str(
            dict(admission_outputs.get("admitted_candidate", {})).get(
                "admitted_candidate_state",
                "",
            )
        ),
        "admitted_candidate_handoff_state": str(
            dict(admission_outputs.get("admitted_candidate_handoff", {})).get(
                "handoff_state",
                "",
            )
        ),
        "admitted_candidate_handoff_ready": bool(
            dict(admission_outputs.get("admitted_candidate_handoff", {})).get(
                "handoff_ready",
                False,
            )
        ),
        "baseline_comparison_state": str(
            dict(admission_outputs.get("baseline_comparison", {})).get(
                "comparison_state",
                "",
            )
        ),
        "baseline_comparison_result_state": str(
            dict(admission_outputs.get("baseline_comparison", {})).get(
                "comparison_result_state",
                "",
            )
        ),
        "stronger_than_current_bounded_baseline": bool(
            dict(admission_outputs.get("baseline_comparison", {})).get(
                "stronger_than_current_bounded_baseline",
                False,
            )
        ),
        "future_reference_target_state": str(
            dict(admission_outputs.get("reference_target", {})).get(
                "reference_target_state",
                "",
            )
        ),
        "future_reference_target_eligible": bool(
            dict(admission_outputs.get("reference_target", {})).get(
                "eligible_as_future_reference_target",
                False,
            )
        ),
        "future_reference_target_id": str(
            dict(admission_outputs.get("reference_target", {})).get(
                "preferred_reference_target_id",
                "",
            )
        ),
        "revised_candidate_state": str(
            revised_candidate_bundle.get("revised_candidate_state", "")
        ),
        "revised_candidate_id": str(
            revised_candidate_bundle.get("revised_candidate_id", "")
        ),
        "revised_candidate_prior_admitted_candidate_id": str(
            revised_candidate_bundle.get("prior_admitted_candidate_id", "")
        ),
        "revised_candidate_materially_stronger_in_aggregate": bool(
            revised_candidate_comparison.get(
                "materially_stronger_than_prior_admitted_candidate_in_aggregate",
                False,
            )
        ),
        "revised_candidate_reference_rollover_state": str(
            revised_candidate_promotion_summary.get("reference_target_rollover_state", "")
        ),
        "reference_target_consumption_state": str(
            reference_target_consumption.get("consumption_state", "")
        ),
        "reference_target_fallback_reason": str(
            reference_target_consumption.get("fallback_reason", "")
        ),
        "active_bounded_reference_target_id": str(
            reference_target_consumption.get("active_bounded_reference_target_id", "")
        ),
        "active_bounded_reference_target_source_kind": str(
            reference_target_consumption.get(
                "active_bounded_reference_target_source_kind",
                "",
            )
        ),
        "active_bounded_reference_target_title": str(
            reference_target_consumption.get("active_bounded_reference_target_title", "")
        ),
        "active_bounded_reference_target_path": str(
            reference_target_consumption.get("active_bounded_reference_target_path", "")
        ),
        "protected_live_baseline_reference_id": str(
            reference_target_consumption.get(
                "protected_live_baseline_reference_id",
                "",
            )
        ),
        "protected_live_baseline_source_kind": str(
            reference_target_consumption.get(
                "protected_live_baseline_source_kind",
                "",
            )
        ),
        "protected_live_baseline_title": str(
            reference_target_consumption.get("protected_live_baseline_title", "")
        ),
        "protected_live_baseline_path_hint": str(
            reference_target_consumption.get("protected_live_baseline_path_hint", "")
        ),
        "reference_target_comparison_basis": str(
            reference_target_consumption.get("comparison_basis", "")
        ),
        "selected_skill_pack_id": str(
            latest_skill_pack_invocation.get("selected_skill_pack_id", "")
        ),
        "selected_skill_pack_title": str(
            latest_skill_pack_invocation.get("selected_skill_pack_title", "")
        ),
        "selected_skill_pack_reason": str(
            latest_skill_pack_invocation.get("selected_reason", "")
        ),
        "skill_pack_result_state": str(
            latest_skill_pack_result.get("result_state", "")
        ),
        "quality_gap_id": str(latest_quality_gap_summary.get("quality_gap_id", "")),
        "quality_gap_title": str(
            latest_quality_gap_summary.get("quality_gap_title", "")
        ),
        "quality_improvement_state": str(
            latest_quality_improvement_summary.get("improvement_state", "")
        ),
        "quality_dimension_id": str(
            latest_quality_improvement_summary.get("quality_dimension_id", "")
        ),
        "quality_dimension_title": str(
            latest_quality_improvement_summary.get("quality_dimension_title", "")
        ),
        "quality_composite_state": str(
            dict(quality_roadmap_outputs.get("composite_evaluation", {})).get(
                "composite_quality_state",
                "",
            )
        ),
        "materially_stronger_than_reference_target_in_aggregate": bool(
            dict(quality_roadmap_outputs.get("composite_evaluation", {})).get(
                "materially_stronger_than_reference_target_in_aggregate",
                False,
            )
        ),
        "quality_weakest_dimension_id": str(
            dict(quality_roadmap_outputs.get("priority_matrix", {})).get(
                "weakest_dimension_id",
                "",
            )
        ),
        "quality_weakest_dimension_title": str(
            dict(quality_roadmap_outputs.get("priority_matrix", {})).get(
                "weakest_dimension_title",
                "",
            )
        ),
        "quality_next_pack_id": str(
            dict(quality_roadmap_outputs.get("next_pack_plan", {})).get(
                "selected_skill_pack_id",
                "",
            )
        ),
        "quality_next_objective_id": str(
            dict(quality_roadmap_outputs.get("next_pack_plan", {})).get(
                "selected_objective_id",
                "",
            )
        ),
        "quality_next_dimension_id": str(
            dict(quality_roadmap_outputs.get("next_pack_plan", {})).get(
                "selected_dimension_id",
                "",
            )
        ),
        "quality_chain_reentry_state": str(
            quality_chain_reentry.get("reentry_state", "")
        ),
        "quality_chain_reentry_reason": str(
            quality_chain_reentry.get("reentry_reason", "")
        ),
        "quality_chain_reentry_action": str(
            quality_chain_reentry.get("recommended_action", "")
        ),
        "quality_chain_next_objective_id": str(
            quality_chain_reentry.get("next_quality_objective_id", "")
        ),
        "quality_chain_next_objective_class": str(
            quality_chain_reentry.get("next_quality_objective_class", "")
        ),
        "quality_chain_next_objective_compact": bool(
            quality_chain_reentry.get("next_quality_objective_compact", False)
        ),
        "generation_index": int(
            dict(generation_progress_outputs.get("generation_history", {})).get(
                "current_generation_index", 0
            )
            or 0
        ),
        "prior_generation_index": int(
            dict(generation_progress_outputs.get("generation_delta", {})).get(
                "prior_generation_index", 0
            )
            or 0
        ),
        "generation_current_candidate_id": str(
            dict(generation_progress_outputs.get("generation_delta", {})).get(
                "current_admitted_candidate_id", ""
            )
        ),
        "generation_prior_candidate_id": str(
            dict(generation_progress_outputs.get("generation_delta", {})).get(
                "prior_admitted_candidate_id", ""
            )
        ),
        "generation_progress_state": str(
            dict(generation_progress_outputs.get("progress_governance", {})).get(
                "progress_state", ""
            )
        ),
        "generation_progress_recommendation_state": str(
            dict(generation_progress_outputs.get("progress_recommendation", {})).get(
                "recommendation_state", ""
            )
        ),
        "generation_additional_improvement_justified": bool(
            dict(generation_progress_outputs.get("progress_governance", {})).get(
                "additional_bounded_improvement_justified", False
            )
        ),
        "generation_remediation_objective_id": str(
            dict(generation_progress_outputs.get("progress_recommendation", {})).get(
                "recommended_objective_id", ""
            )
        ),
        "strategy_selection_state": str(
            dict(strategy_selection_outputs.get("strategy_selection", {})).get(
                "selected_strategy_state", ""
            )
        ),
        "strategy_follow_on_family": str(
            dict(strategy_selection_outputs.get("strategy_follow_on_plan", {})).get(
                "follow_on_family", ""
            )
        ),
        "strategy_operator_review_recommended": bool(
            dict(strategy_selection_outputs.get("strategy_follow_on_plan", {})).get(
                "operator_review_recommended_before_execution", False
            )
        ),
        "strategy_selected_objective_id": str(
            dict(strategy_selection_outputs.get("strategy_follow_on_plan", {})).get(
                "recommended_objective_id", ""
            )
        ),
        "strategy_selected_objective_class": str(
            dict(strategy_selection_outputs.get("strategy_follow_on_plan", {})).get(
                "recommended_objective_class", ""
            )
        ),
        "strategy_selected_skill_pack_id": str(
            dict(strategy_selection_outputs.get("strategy_follow_on_plan", {})).get(
                "recommended_skill_pack_id", ""
            )
        ),
        "strategy_selected_dimension_id": str(
            dict(strategy_selection_outputs.get("strategy_follow_on_plan", {})).get(
                "recommended_dimension_id", ""
            )
        ),
        "strategy_rationale_summary": str(
            dict(strategy_selection_outputs.get("strategy_rationale", {})).get(
                "selected_strategy_rationale", ""
            )
        ),
        "latest_successor_campaign_history_path": str(
            campaign_governance_outputs.get("campaign_history_path", "")
        ),
        "latest_successor_campaign_delta_path": str(
            campaign_governance_outputs.get("campaign_delta_path", "")
        ),
        "latest_successor_campaign_governance_path": str(
            campaign_governance_outputs.get("campaign_governance_path", "")
        ),
        "latest_successor_campaign_recommendation_path": str(
            campaign_governance_outputs.get("campaign_recommendation_path", "")
        ),
        "latest_successor_campaign_wave_plan_path": str(
            campaign_governance_outputs.get("campaign_wave_plan_path", "")
        ),
        "latest_successor_campaign_cycle_history_path": str(
            campaign_cycle_governance_outputs.get("campaign_cycle_history_path", "")
        ),
        "latest_successor_campaign_cycle_delta_path": str(
            campaign_cycle_governance_outputs.get("campaign_cycle_delta_path", "")
        ),
        "latest_successor_campaign_cycle_governance_path": str(
            campaign_cycle_governance_outputs.get("campaign_cycle_governance_path", "")
        ),
        "latest_successor_campaign_cycle_recommendation_path": str(
            campaign_cycle_governance_outputs.get(
                "campaign_cycle_recommendation_path", ""
            )
        ),
        "latest_successor_campaign_cycle_follow_on_plan_path": str(
            campaign_cycle_governance_outputs.get(
                "campaign_cycle_follow_on_plan_path", ""
            )
        ),
        "campaign_id": str(
            dict(campaign_governance_outputs.get("campaign_history", {})).get(
                "current_campaign_id", ""
            )
        ),
        "campaign_wave_count": int(
            dict(campaign_governance_outputs.get("campaign_history", {})).get(
                "current_campaign_wave_count", 0
            )
            or 0
        ),
        "campaign_progress_state": str(
            dict(campaign_governance_outputs.get("campaign_governance", {})).get(
                "campaign_progress_state", ""
            )
        ),
        "campaign_state": str(
            dict(campaign_governance_outputs.get("campaign_governance", {})).get(
                "campaign_state", ""
            )
        ),
        "campaign_recommendation_state": str(
            dict(campaign_governance_outputs.get("campaign_recommendation", {})).get(
                "recommendation_state", ""
            )
        ),
        "campaign_follow_on_family": str(
            dict(campaign_governance_outputs.get("campaign_wave_plan", {})).get(
                "recommended_follow_on_family", ""
            )
        ),
        "campaign_refresh_revised_candidate_ready": bool(
            dict(campaign_governance_outputs.get("campaign_governance", {})).get(
                "refresh_revised_candidate_justified", False
            )
        ),
        "campaign_last_wave_strategy_state": str(
            dict(campaign_governance_outputs.get("campaign_delta", {})).get(
                "last_wave_strategy_state", ""
            )
        ),
        "campaign_last_wave_skill_pack_id": str(
            dict(campaign_governance_outputs.get("campaign_delta", {})).get(
                "last_wave_skill_pack_id", ""
            )
        ),
        "campaign_accumulated_improved_dimension_ids": list(
            dict(campaign_governance_outputs.get("campaign_governance", {})).get(
                "accumulated_improved_dimension_ids", []
            )
        ),
        "campaign_remaining_weak_dimension_ids": list(
            dict(campaign_governance_outputs.get("campaign_governance", {})).get(
                "remaining_weak_dimension_ids", []
            )
        ),
        "campaign_cycle_id": str(
            dict(campaign_cycle_governance_outputs.get("campaign_cycle_history", {})).get(
                "current_campaign_cycle_id", ""
            )
        ),
        "campaign_cycle_index": int(
            dict(campaign_cycle_governance_outputs.get("campaign_cycle_history", {})).get(
                "current_campaign_cycle_index", 0
            )
            or 0
        ),
        "prior_campaign_cycle_index": int(
            dict(campaign_cycle_governance_outputs.get("campaign_cycle_delta", {})).get(
                "prior_campaign_cycle_index", 0
            )
            or 0
        ),
        "campaign_cycle_progress_state": str(
            dict(
                campaign_cycle_governance_outputs.get("campaign_cycle_governance", {})
            ).get("campaign_cycle_progress_state", "")
        ),
        "campaign_cycle_state": str(
            dict(
                campaign_cycle_governance_outputs.get("campaign_cycle_governance", {})
            ).get("campaign_cycle_state", "")
        ),
        "campaign_cycle_recommendation_state": str(
            dict(
                campaign_cycle_governance_outputs.get(
                    "campaign_cycle_recommendation", {}
                )
            ).get("recommendation_state", "")
        ),
        "campaign_cycle_follow_on_family": str(
            dict(
                campaign_cycle_governance_outputs.get(
                    "campaign_cycle_follow_on_plan", {}
                )
            ).get("recommended_follow_on_family", "")
        ),
        "campaign_cycle_current_reference_target_id": str(
            dict(campaign_cycle_governance_outputs.get("campaign_cycle_delta", {})).get(
                "current_reference_target_id", ""
            )
        ),
        "campaign_cycle_prior_reference_target_id": str(
            dict(campaign_cycle_governance_outputs.get("campaign_cycle_delta", {})).get(
                "prior_reference_target_id", ""
            )
        ),
        "campaign_cycle_source_campaign_id": str(
            dict(campaign_cycle_governance_outputs.get("campaign_cycle_delta", {})).get(
                "source_campaign_id", ""
            )
        ),
        "campaign_cycle_new_dimension_ids": list(
            dict(
                campaign_cycle_governance_outputs.get("campaign_cycle_governance", {})
            ).get("new_dimension_ids_vs_prior_cycle", [])
        ),
        "campaign_cycle_remaining_weak_dimension_ids": list(
            dict(
                campaign_cycle_governance_outputs.get("campaign_cycle_governance", {})
            ).get("remaining_weak_dimension_ids", [])
        ),
        "latest_successor_loop_history_path": str(
            loop_governance_outputs.get("loop_history_path", "")
        ),
        "latest_successor_loop_delta_path": str(
            loop_governance_outputs.get("loop_delta_path", "")
        ),
        "latest_successor_loop_governance_path": str(
            loop_governance_outputs.get("loop_governance_path", "")
        ),
        "latest_successor_loop_recommendation_path": str(
            loop_governance_outputs.get("loop_recommendation_path", "")
        ),
        "latest_successor_loop_follow_on_plan_path": str(
            loop_governance_outputs.get("loop_follow_on_plan_path", "")
        ),
        "loop_id": str(
            dict(loop_governance_outputs.get("loop_history", {})).get(
                "current_loop_id", ""
            )
        ),
        "loop_index": int(
            dict(loop_governance_outputs.get("loop_history", {})).get(
                "current_loop_index", 0
            )
            or 0
        ),
        "prior_loop_index": int(
            dict(loop_governance_outputs.get("loop_delta", {})).get(
                "prior_loop_index", 0
            )
            or 0
        ),
        "loop_progress_state": str(
            dict(loop_governance_outputs.get("loop_governance", {})).get(
                "loop_progress_state", ""
            )
        ),
        "loop_state": str(
            dict(loop_governance_outputs.get("loop_governance", {})).get(
                "loop_state", ""
            )
        ),
        "loop_recommendation_state": str(
            dict(loop_governance_outputs.get("loop_recommendation", {})).get(
                "recommendation_state", ""
            )
        ),
        "loop_follow_on_family": str(
            dict(loop_governance_outputs.get("loop_follow_on_plan", {})).get(
                "recommended_follow_on_family", ""
            )
        ),
        "loop_current_reference_target_id": str(
            dict(loop_governance_outputs.get("loop_delta", {})).get(
                "current_reference_target_id", ""
            )
        ),
        "loop_prior_reference_target_id": str(
            dict(loop_governance_outputs.get("loop_delta", {})).get(
                "prior_reference_target_id", ""
            )
        ),
        "loop_source_campaign_cycle_id": str(
            dict(loop_governance_outputs.get("loop_delta", {})).get(
                "source_campaign_cycle_id", ""
            )
        ),
        "loop_new_dimension_ids": list(
            dict(loop_governance_outputs.get("loop_governance", {})).get(
                "new_dimension_ids_vs_prior_loop", []
            )
        ),
        "loop_remaining_weak_dimension_ids": list(
            dict(loop_governance_outputs.get("loop_governance", {})).get(
                "remaining_weak_dimension_ids", []
            )
        ),
        "reseed_state": str(
            dict(reseed_outputs.get("effective_next_objective", {})).get(
                "reseed_state",
                dict(reseed_outputs.get("request", {})).get("reseed_state", ""),
            )
        ),
        "continuation_authorized": bool(
            dict(reseed_outputs.get("effective_next_objective", {})).get(
                "continuation_authorized", False
            )
        ),
        "effective_next_objective_id": str(
            dict(reseed_outputs.get("effective_next_objective", {})).get("objective_id", "")
        ),
        "effective_next_objective_class": str(
            dict(reseed_outputs.get("effective_next_objective", {})).get("objective_class", "")
        ),
        "effective_next_objective_authorization_origin": str(
            dict(reseed_outputs.get("effective_next_objective", {})).get("authorization_origin", "")
        ),
        "latest_successor_auto_continue_policy_path": str(
            auto_continue_outputs.get("policy_path", "")
        ),
        "latest_successor_auto_continue_state_path": str(
            auto_continue_outputs.get("state_path", "")
        ),
        "latest_successor_auto_continue_decision_path": str(
            auto_continue_outputs.get("decision_path", "")
        ),
        "auto_continue_enabled": bool(
            dict(auto_continue_outputs.get("policy", {})).get("enabled", False)
        ),
        "auto_continue_allowed_objective_classes": list(
            dict(auto_continue_outputs.get("policy", {})).get("allowed_objective_classes", [])
        ),
        "auto_continue_chain_count": int(
            dict(auto_continue_outputs.get("state", {})).get("current_chain_count", 0) or 0
        ),
        "auto_continue_chain_cap": int(
            dict(auto_continue_outputs.get("policy", {})).get("max_auto_continue_chain_length", 1)
            or 1
        ),
        "auto_continue_last_reason": str(auto_continue_outputs.get("reason", "")),
        "auto_continue_last_origin": str(auto_continue_outputs.get("authorization_origin", "")),
        "budget_staging_decision": latest_budget_staging_decision,
        "budget_staging_rationale": latest_budget_staging_rationale,
        "budget_staging_objective_id": latest_budget_staging_objective_id,
        "budget_staging_objective_class": latest_budget_staging_objective_class,
        "latest_auto_continue_transition_path": latest_auto_continue_transition_path,
        "auto_continue_transition_state": latest_auto_continue_transition_state,
        "auto_continue_transition_executed_in_session": bool(
            latest_auto_continue_transition_state == AUTO_CONTINUE_TRANSITION_STARTED
        ),
        "auto_continue_transition_from_objective_id": latest_auto_continue_transition_from_objective_id,
        "auto_continue_transition_to_objective_id": latest_auto_continue_transition_to_objective_id,
        "auto_continue_transition_cycle_index": int(latest_auto_continue_transition_cycle_index or 0),
        "cycle_rows": cycle_rows,
        "successor_review_summary": dict(review_outputs.get("review_summary", {})),
        "successor_promotion_recommendation": dict(review_outputs.get("promotion_recommendation", {})),
        "successor_next_objective_proposal": dict(review_outputs.get("next_objective_proposal", {})),
        "successor_reseed_request": dict(reseed_outputs.get("request", {})),
        "successor_reseed_decision": dict(reseed_outputs.get("decision", {})),
        "successor_continuation_lineage": dict(reseed_outputs.get("continuation_lineage", {})),
        "successor_effective_next_objective": dict(reseed_outputs.get("effective_next_objective", {})),
        "successor_baseline_admission_review": dict(admission_outputs.get("review", {})),
        "successor_baseline_admission_recommendation": dict(
            admission_outputs.get("recommendation", {})
        ),
        "successor_baseline_admission_decision": dict(admission_outputs.get("decision", {})),
        "successor_baseline_remediation_proposal": dict(
            admission_outputs.get("remediation_proposal", {})
        ),
        "successor_admitted_candidate": dict(admission_outputs.get("admitted_candidate", {})),
        "successor_admitted_candidate_handoff": dict(
            admission_outputs.get("admitted_candidate_handoff", {})
        ),
        "successor_baseline_comparison": dict(
            admission_outputs.get("baseline_comparison", {})
        ),
        "successor_reference_target": dict(admission_outputs.get("reference_target", {})),
        "successor_revised_candidate_bundle": dict(revised_candidate_bundle),
        "successor_revised_candidate_handoff": dict(revised_candidate_handoff),
        "successor_revised_candidate_comparison": dict(revised_candidate_comparison),
        "successor_revised_candidate_promotion_summary": dict(
            revised_candidate_promotion_summary
        ),
        "successor_reference_target_consumption": dict(reference_target_consumption),
        "successor_skill_pack_invocation": dict(latest_skill_pack_invocation),
        "successor_skill_pack_result": dict(latest_skill_pack_result),
        "successor_quality_gap_summary": dict(latest_quality_gap_summary),
        "successor_quality_improvement_summary": dict(
            latest_quality_improvement_summary
        ),
        "successor_quality_roadmap": dict(quality_roadmap_outputs.get("roadmap", {})),
        "successor_quality_priority_matrix": dict(
            quality_roadmap_outputs.get("priority_matrix", {})
        ),
        "successor_quality_composite_evaluation": dict(
            quality_roadmap_outputs.get("composite_evaluation", {})
        ),
        "successor_quality_next_pack_plan": dict(
            quality_roadmap_outputs.get("next_pack_plan", {})
        ),
        "successor_quality_chain_reentry": dict(quality_chain_reentry),
        "successor_generation_history": dict(
            generation_progress_outputs.get("generation_history", {})
        ),
        "successor_generation_delta": dict(
            generation_progress_outputs.get("generation_delta", {})
        ),
        "successor_progress_governance": dict(
            generation_progress_outputs.get("progress_governance", {})
        ),
        "successor_progress_recommendation": dict(
            generation_progress_outputs.get("progress_recommendation", {})
        ),
        "successor_strategy_selection": dict(
            strategy_selection_outputs.get("strategy_selection", {})
        ),
        "successor_strategy_rationale": dict(
            strategy_selection_outputs.get("strategy_rationale", {})
        ),
        "successor_strategy_follow_on_plan": dict(
            strategy_selection_outputs.get("strategy_follow_on_plan", {})
        ),
        "successor_strategy_decision_support": dict(
            strategy_selection_outputs.get("strategy_decision_support", {})
        ),
        "successor_campaign_history": dict(
            campaign_governance_outputs.get("campaign_history", {})
        ),
        "successor_campaign_delta": dict(
            campaign_governance_outputs.get("campaign_delta", {})
        ),
        "successor_campaign_governance": dict(
            campaign_governance_outputs.get("campaign_governance", {})
        ),
        "successor_campaign_recommendation": dict(
            campaign_governance_outputs.get("campaign_recommendation", {})
        ),
        "successor_campaign_wave_plan": dict(
            campaign_governance_outputs.get("campaign_wave_plan", {})
        ),
        "successor_campaign_cycle_history": dict(
            campaign_cycle_governance_outputs.get("campaign_cycle_history", {})
        ),
        "successor_campaign_cycle_delta": dict(
            campaign_cycle_governance_outputs.get("campaign_cycle_delta", {})
        ),
        "successor_campaign_cycle_governance": dict(
            campaign_cycle_governance_outputs.get("campaign_cycle_governance", {})
        ),
        "successor_campaign_cycle_recommendation": dict(
            campaign_cycle_governance_outputs.get(
                "campaign_cycle_recommendation", {}
            )
        ),
        "successor_campaign_cycle_follow_on_plan": dict(
            campaign_cycle_governance_outputs.get(
                "campaign_cycle_follow_on_plan", {}
            )
        ),
        "successor_loop_history": dict(
            loop_governance_outputs.get("loop_history", {})
        ),
        "successor_loop_delta": dict(loop_governance_outputs.get("loop_delta", {})),
        "successor_loop_governance": dict(
            loop_governance_outputs.get("loop_governance", {})
        ),
        "successor_loop_recommendation": dict(
            loop_governance_outputs.get("loop_recommendation", {})
        ),
        "successor_loop_follow_on_plan": dict(
            loop_governance_outputs.get("loop_follow_on_plan", {})
        ),
        "successor_auto_continue_policy": dict(auto_continue_outputs.get("policy", {})),
        "successor_auto_continue_state": dict(auto_continue_outputs.get("state", {})),
        "successor_auto_continue_decision": dict(auto_continue_outputs.get("decision", {})),
    }
    controller_summary_path.write_text(_dump(controller_summary), encoding="utf-8")

    if paths["workspace_artifact_index_path"].exists():
        workspace_artifact_index = _build_workspace_artifact_index_payload(workspace_root)
        _write_json(
            paths["workspace_artifact_index_path"],
            workspace_artifact_index,
            log_path=runtime_event_log_path,
            session_id=session_id,
            directive_id=directive_id,
            execution_profile=execution_profile,
            workspace_id=workspace_id,
            workspace_root=str(workspace_root),
            work_item_id="governed_execution_controller",
            artifact_kind="workspace_artifact_index_json",
        )

    final_reason = str(current_payload.get("reason", "")).strip()
    if stop_reason == STOP_REASON_COMPLETED:
        final_reason = (
            "completed bounded governed execution by directive-derived stop condition after "
            f"{int(controller_budget_overview.get('counted_cycle_count', 0) or 0)} counted cycle(s)"
            + (
                f" plus {int(controller_budget_overview.get('staged_compact_follow_on_count', 0) or 0)} staged compact follow-on objective(s)"
                if int(controller_budget_overview.get("staged_compact_follow_on_count", 0) or 0) > 0
                else ""
            )
            + "; operator review is still required before any promotion or next-objective continuation"
        )
    elif stop_reason == STOP_REASON_MAX_CAP:
        final_reason = stop_detail
    elif stop_reason == STOP_REASON_SINGLE_CYCLE:
        final_reason = stop_detail
    elif not final_reason:
        final_reason = stop_detail

    current_payload["generated_at"] = _now()
    if stop_reason == STOP_REASON_COMPLETED and not cycle_rows:
        current_payload["status"] = STOP_REASON_COMPLETED
    elif stop_reason == STOP_REASON_NO_WORK and not cycle_rows:
        current_payload["status"] = STOP_REASON_NO_WORK
    elif stop_reason == STOP_REASON_MAX_CAP:
        current_payload["status"] = STOP_REASON_MAX_CAP
    current_payload["reason"] = final_reason
    current_payload["governed_execution_controller"] = controller_summary
    current_payload["controller_artifact_path"] = str(controller_summary_path)
    current_payload["successor_review"] = dict(review_outputs.get("review_summary", {}))
    current_payload["successor_promotion_recommendation"] = dict(
        review_outputs.get("promotion_recommendation", {})
    )
    current_payload["successor_next_objective_proposal"] = dict(
        review_outputs.get("next_objective_proposal", {})
    )
    current_payload["successor_reseed_request"] = dict(reseed_outputs.get("request", {}))
    current_payload["successor_reseed_decision"] = dict(reseed_outputs.get("decision", {}))
    current_payload["successor_continuation_lineage"] = dict(
        reseed_outputs.get("continuation_lineage", {})
    )
    current_payload["successor_effective_next_objective"] = dict(
        reseed_outputs.get("effective_next_objective", {})
    )
    current_payload["successor_baseline_admission_review"] = dict(
        admission_outputs.get("review", {})
    )
    current_payload["successor_baseline_admission_recommendation"] = dict(
        admission_outputs.get("recommendation", {})
    )
    current_payload["successor_baseline_admission_decision"] = dict(
        admission_outputs.get("decision", {})
    )
    current_payload["successor_baseline_remediation_proposal"] = dict(
        admission_outputs.get("remediation_proposal", {})
    )
    current_payload["successor_admitted_candidate"] = dict(
        admission_outputs.get("admitted_candidate", {})
    )
    current_payload["successor_admitted_candidate_handoff"] = dict(
        admission_outputs.get("admitted_candidate_handoff", {})
    )
    current_payload["successor_baseline_comparison"] = dict(
        admission_outputs.get("baseline_comparison", {})
    )
    current_payload["successor_reference_target"] = dict(
        admission_outputs.get("reference_target", {})
    )
    current_payload["successor_revised_candidate_bundle"] = dict(
        revised_candidate_bundle
    )
    current_payload["successor_revised_candidate_handoff"] = dict(
        revised_candidate_handoff
    )
    current_payload["successor_revised_candidate_comparison"] = dict(
        revised_candidate_comparison
    )
    current_payload["successor_revised_candidate_promotion_summary"] = dict(
        revised_candidate_promotion_summary
    )
    current_payload["successor_reference_target_consumption"] = dict(
        reference_target_consumption
    )
    current_payload["successor_skill_pack_invocation"] = dict(
        latest_skill_pack_invocation
    )
    current_payload["successor_skill_pack_result"] = dict(latest_skill_pack_result)
    current_payload["successor_quality_gap_summary"] = dict(
        latest_quality_gap_summary
    )
    current_payload["successor_quality_improvement_summary"] = dict(
        latest_quality_improvement_summary
    )
    current_payload["successor_quality_roadmap"] = dict(
        quality_roadmap_outputs.get("roadmap", {})
    )
    current_payload["successor_quality_priority_matrix"] = dict(
        quality_roadmap_outputs.get("priority_matrix", {})
    )
    current_payload["successor_quality_composite_evaluation"] = dict(
        quality_roadmap_outputs.get("composite_evaluation", {})
    )
    current_payload["successor_quality_next_pack_plan"] = dict(
        quality_roadmap_outputs.get("next_pack_plan", {})
    )
    current_payload["successor_quality_chain_reentry"] = dict(quality_chain_reentry)
    current_payload["successor_generation_history"] = dict(
        generation_progress_outputs.get("generation_history", {})
    )
    current_payload["successor_generation_delta"] = dict(
        generation_progress_outputs.get("generation_delta", {})
    )
    current_payload["successor_progress_governance"] = dict(
        generation_progress_outputs.get("progress_governance", {})
    )
    current_payload["successor_progress_recommendation"] = dict(
        generation_progress_outputs.get("progress_recommendation", {})
    )
    current_payload["successor_strategy_selection"] = dict(
        strategy_selection_outputs.get("strategy_selection", {})
    )
    current_payload["successor_strategy_rationale"] = dict(
        strategy_selection_outputs.get("strategy_rationale", {})
    )
    current_payload["successor_strategy_follow_on_plan"] = dict(
        strategy_selection_outputs.get("strategy_follow_on_plan", {})
    )
    current_payload["successor_strategy_decision_support"] = dict(
        strategy_selection_outputs.get("strategy_decision_support", {})
    )
    current_payload["successor_campaign_history"] = dict(
        campaign_governance_outputs.get("campaign_history", {})
    )
    current_payload["successor_campaign_delta"] = dict(
        campaign_governance_outputs.get("campaign_delta", {})
    )
    current_payload["successor_campaign_governance"] = dict(
        campaign_governance_outputs.get("campaign_governance", {})
    )
    current_payload["successor_campaign_recommendation"] = dict(
        campaign_governance_outputs.get("campaign_recommendation", {})
    )
    current_payload["successor_campaign_wave_plan"] = dict(
        campaign_governance_outputs.get("campaign_wave_plan", {})
    )
    current_payload["successor_campaign_cycle_history"] = dict(
        campaign_cycle_governance_outputs.get("campaign_cycle_history", {})
    )
    current_payload["successor_campaign_cycle_delta"] = dict(
        campaign_cycle_governance_outputs.get("campaign_cycle_delta", {})
    )
    current_payload["successor_campaign_cycle_governance"] = dict(
        campaign_cycle_governance_outputs.get("campaign_cycle_governance", {})
    )
    current_payload["successor_campaign_cycle_recommendation"] = dict(
        campaign_cycle_governance_outputs.get("campaign_cycle_recommendation", {})
    )
    current_payload["successor_campaign_cycle_follow_on_plan"] = dict(
        campaign_cycle_governance_outputs.get("campaign_cycle_follow_on_plan", {})
    )
    current_payload["successor_loop_history"] = dict(
        loop_governance_outputs.get("loop_history", {})
    )
    current_payload["successor_loop_delta"] = dict(
        loop_governance_outputs.get("loop_delta", {})
    )
    current_payload["successor_loop_governance"] = dict(
        loop_governance_outputs.get("loop_governance", {})
    )
    current_payload["successor_loop_recommendation"] = dict(
        loop_governance_outputs.get("loop_recommendation", {})
    )
    current_payload["successor_loop_follow_on_plan"] = dict(
        loop_governance_outputs.get("loop_follow_on_plan", {})
    )
    current_payload["successor_auto_continue_policy"] = dict(
        auto_continue_outputs.get("policy", {})
    )
    current_payload["successor_auto_continue_state"] = dict(
        auto_continue_outputs.get("state", {})
    )
    current_payload["successor_auto_continue_decision"] = dict(
        auto_continue_outputs.get("decision", {})
    )

    brief_lines = [
        "# Governed Execution Brief",
        "",
        f"Status: {current_payload.get('status', '')}",
        f"Directive ID: `{directive_id}`",
        f"Workspace: `{workspace_id} -> {workspace_root}`",
        f"Controller mode: `{controller_mode}`",
        f"Invocation model: `{invocation_model}`",
        f"Counted cycles completed: `{int(controller_budget_overview.get('counted_cycle_count', 0) or 0)}`",
        f"Staged compact follow-ons: `{int(controller_budget_overview.get('staged_compact_follow_on_count', 0) or 0)}`",
        f"Remaining counted cycle budget: `{int(controller_budget_overview.get('remaining_counted_cycle_budget', 0) or 0)}`",
        f"Current objective source: `{current_objective.get('source_kind', '') or '<none>'}`",
        f"Current objective id: `{current_objective.get('objective_id', '') or '<none>'}`",
        f"Current objective class: `{current_objective.get('objective_class', '') or '<none>'}`",
        f"Stop reason: `{stop_reason}`",
        f"Latest cycle kind: `{latest_cycle_kind or '<none>'}`",
        f"Review status: `{dict(review_outputs.get('review_summary', {})).get('review_status', '') or '<none>'}`",
        f"Promotion recommendation: `{dict(review_outputs.get('promotion_recommendation', {})).get('promotion_recommendation_state', '') or '<none>'}`",
        f"Next objective proposal: `{dict(review_outputs.get('next_objective_proposal', {})).get('objective_id', '') or '<none>'}`",
        f"Next objective class: `{dict(review_outputs.get('next_objective_proposal', {})).get('objective_class', '') or '<none>'}`",
        f"Baseline admission review: `{dict(admission_outputs.get('review', {})).get('admission_review_state', '') or '<none>'}`",
        f"Baseline admission recommendation: `{dict(admission_outputs.get('recommendation', {})).get('admission_recommendation_state', '') or '<none>'}`",
        f"Baseline admission decision: `{dict(admission_outputs.get('decision', {})).get('admission_decision_state', '') or '<none>'}`",
        f"Baseline remediation proposal: `{dict(admission_outputs.get('remediation_proposal', {})).get('objective_id', '') or '<none>'}`",
        f"Future reference target: `{dict(admission_outputs.get('reference_target', {})).get('reference_target_state', '') or '<none>'}`",
        f"Revised candidate state: `{str(revised_candidate_bundle.get('revised_candidate_state', '') or '<none>')}`",
        f"Revised candidate id: `{str(revised_candidate_bundle.get('revised_candidate_id', '') or '<none>')}`",
        f"Revised candidate rollover: `{str(revised_candidate_promotion_summary.get('reference_target_rollover_state', '') or '<none>')}`",
        f"Reference target consumption: `{reference_target_consumption.get('consumption_state', '') or '<none>'}`",
        f"Active bounded reference target: `{reference_target_consumption.get('active_bounded_reference_target_id', '') or '<none>'}`",
        f"Protected live baseline: `{reference_target_consumption.get('protected_live_baseline_reference_id', '') or '<none>'}`",
        f"Selected skill pack: `{latest_skill_pack_invocation.get('selected_skill_pack_id', '') or '<none>'}`",
        f"Skill-pack result: `{latest_skill_pack_result.get('result_state', '') or '<none>'}`",
        f"Quality gap: `{latest_quality_gap_summary.get('quality_gap_id', '') or '<none>'}`",
        f"Quality improvement: `{latest_quality_improvement_summary.get('improvement_state', '') or '<none>'}`",
        "Quality roadmap weakest dimension: "
        f"`{dict(quality_roadmap_outputs.get('priority_matrix', {})).get('weakest_dimension_id', '') or '<none>'}`",
        "Quality composite state: "
        f"`{dict(quality_roadmap_outputs.get('composite_evaluation', {})).get('composite_quality_state', '') or '<none>'}`",
        "Quality next pack: "
        f"`{dict(quality_roadmap_outputs.get('next_pack_plan', {})).get('selected_skill_pack_id', '') or '<none>'}`",
        "Campaign id: "
        f"`{dict(campaign_governance_outputs.get('campaign_history', {})).get('current_campaign_id', '') or '<none>'}`",
        "Campaign wave count: "
        f"`{int(dict(campaign_governance_outputs.get('campaign_history', {})).get('current_campaign_wave_count', 0) or 0)}`",
        "Campaign progress state: "
        f"`{dict(campaign_governance_outputs.get('campaign_governance', {})).get('campaign_progress_state', '') or '<none>'}`",
        "Campaign recommendation: "
        f"`{dict(campaign_governance_outputs.get('campaign_recommendation', {})).get('recommendation_state', '') or '<none>'}`",
        "Campaign follow-on family: "
        f"`{dict(campaign_governance_outputs.get('campaign_wave_plan', {})).get('recommended_follow_on_family', '') or '<none>'}`",
        "Campaign refresh ready: "
        f"`{bool(dict(campaign_governance_outputs.get('campaign_governance', {})).get('refresh_revised_candidate_justified', False))}`",
        "Campaign-cycle id: "
        f"`{dict(campaign_cycle_governance_outputs.get('campaign_cycle_history', {})).get('current_campaign_cycle_id', '') or '<none>'}`",
        "Campaign-cycle index: "
        f"`{int(dict(campaign_cycle_governance_outputs.get('campaign_cycle_history', {})).get('current_campaign_cycle_index', 0) or 0)}`",
        "Campaign-cycle progress state: "
        f"`{dict(campaign_cycle_governance_outputs.get('campaign_cycle_governance', {})).get('campaign_cycle_progress_state', '') or '<none>'}`",
        "Campaign-cycle recommendation: "
        f"`{dict(campaign_cycle_governance_outputs.get('campaign_cycle_recommendation', {})).get('recommendation_state', '') or '<none>'}`",
        "Campaign-cycle follow-on family: "
        f"`{dict(campaign_cycle_governance_outputs.get('campaign_cycle_follow_on_plan', {})).get('recommended_follow_on_family', '') or '<none>'}`",
        "Loop id: "
        f"`{dict(loop_governance_outputs.get('loop_history', {})).get('current_loop_id', '') or '<none>'}`",
        "Loop index: "
        f"`{int(dict(loop_governance_outputs.get('loop_history', {})).get('current_loop_index', 0) or 0)}`",
        "Loop progress state: "
        f"`{dict(loop_governance_outputs.get('loop_governance', {})).get('loop_progress_state', '') or '<none>'}`",
        "Loop recommendation: "
        f"`{dict(loop_governance_outputs.get('loop_recommendation', {})).get('recommendation_state', '') or '<none>'}`",
        "Loop follow-on family: "
        f"`{dict(loop_governance_outputs.get('loop_follow_on_plan', {})).get('recommended_follow_on_family', '') or '<none>'}`",
        f"Reseed state: `{dict(reseed_outputs.get('effective_next_objective', {})).get('reseed_state', '') or dict(reseed_outputs.get('request', {})).get('reseed_state', '') or '<none>'}`",
        f"Continuation authorized: `{bool(dict(reseed_outputs.get('effective_next_objective', {})).get('continuation_authorized', False))}`",
        f"Auto-continue enabled: `{bool(dict(auto_continue_outputs.get('policy', {})).get('enabled', False))}`",
        f"Auto-continue reason: `{str(auto_continue_outputs.get('reason', '') or '<none>')}`",
        f"Auto-continue chain: `{int(dict(auto_continue_outputs.get('state', {})).get('current_chain_count', 0) or 0)}/{int(dict(auto_continue_outputs.get('policy', {})).get('max_auto_continue_chain_length', 1) or 1)}`",
        f"Budget staging decision: `{latest_budget_staging_decision or '<none>'}`",
        f"Budget staging objective: `{latest_budget_staging_objective_id or '<none>'}`",
        f"Latest summary artifact: `{latest_summary_artifact_path or '<none>'}`",
        f"Controller summary: `{controller_summary_path}`",
        f"Review summary: `{str(review_outputs.get('review_summary_path', '')) or '<none>'}`",
        f"Baseline admission decision: `{str(admission_outputs.get('decision_path', '')) or '<none>'}`",
        f"Revised candidate bundle: `{str(paths['revised_candidate_bundle_path'])}`",
        f"Revised candidate comparison: `{str(paths['revised_candidate_comparison_path'])}`",
        f"Reference target consumption: `{str(paths['reference_target_consumption_path'])}`",
        f"Skill-pack invocation: `{str(paths['skill_pack_invocation_path'])}`",
        f"Skill-pack result: `{str(paths['skill_pack_result_path'])}`",
        f"Quality gap summary: `{str(paths['quality_gap_summary_path'])}`",
        f"Quality improvement summary: `{str(paths['quality_improvement_summary_path'])}`",
        f"Quality roadmap: `{str(paths['quality_roadmap_path'])}`",
        f"Quality priority matrix: `{str(paths['quality_priority_matrix_path'])}`",
        f"Quality composite evaluation: `{str(paths['quality_composite_evaluation_path'])}`",
        f"Quality next-pack plan: `{str(paths['quality_next_pack_plan_path'])}`",
        f"Campaign history: `{str(paths['campaign_history_path'])}`",
        f"Campaign delta: `{str(paths['campaign_delta_path'])}`",
        f"Campaign governance: `{str(paths['campaign_governance_path'])}`",
        f"Campaign recommendation: `{str(paths['campaign_recommendation_path'])}`",
        f"Campaign wave plan: `{str(paths['campaign_wave_plan_path'])}`",
        f"Campaign-cycle history: `{str(paths['campaign_cycle_history_path'])}`",
        f"Campaign-cycle delta: `{str(paths['campaign_cycle_delta_path'])}`",
        f"Campaign-cycle governance: `{str(paths['campaign_cycle_governance_path'])}`",
        f"Campaign-cycle recommendation: `{str(paths['campaign_cycle_recommendation_path'])}`",
        f"Campaign-cycle follow-on plan: `{str(paths['campaign_cycle_follow_on_plan_path'])}`",
        f"Loop history: `{str(paths['loop_history_path'])}`",
        f"Loop delta: `{str(paths['loop_delta_path'])}`",
        f"Loop governance: `{str(paths['loop_governance_path'])}`",
        f"Loop recommendation: `{str(paths['loop_recommendation_path'])}`",
        f"Loop follow-on plan: `{str(paths['loop_follow_on_plan_path'])}`",
        f"Auto-continue state: `{str(auto_continue_outputs.get('state_path', '')) or '<none>'}`",
    ]
    _finalize_session_artifacts(
        payload=current_payload,
        session_artifact_path=session_artifact_path,
        session_archive_path=session_archive_path,
        brief_path=brief_path,
        brief_lines=brief_lines,
    )
    _event(
        runtime_event_log_path,
        event_type="governed_execution_controller_stopped",
        session_id=session_id,
        directive_id=directive_id,
        execution_profile=execution_profile,
        workspace_id=workspace_id,
        workspace_root=str(workspace_root),
        controller_mode=str(controller_mode),
        invocation_model=invocation_model,
        cycles_completed=int(controller_budget_overview.get("counted_cycle_count", 0) or 0),
        staged_compact_follow_on_count=int(
            controller_budget_overview.get("staged_compact_follow_on_count", 0) or 0
        ),
        total_executed_objective_rows=int(
            controller_budget_overview.get("total_objective_rows", 0) or 0
        ),
        remaining_counted_cycle_budget=int(
            controller_budget_overview.get("remaining_counted_cycle_budget", 0) or 0
        ),
        latest_cycle_index=latest_cycle_index,
        stop_reason=stop_reason,
        stop_detail=stop_detail,
        budget_staging_decision=latest_budget_staging_decision,
        budget_staging_rationale=latest_budget_staging_rationale,
        budget_staging_objective_id=latest_budget_staging_objective_id,
        budget_staging_objective_class=latest_budget_staging_objective_class,
        reference_target_consumption_state=str(
            reference_target_consumption.get("consumption_state", "")
        ),
        active_bounded_reference_target_id=str(
            reference_target_consumption.get("active_bounded_reference_target_id", "")
        ),
        protected_live_baseline_reference_id=str(
            reference_target_consumption.get("protected_live_baseline_reference_id", "")
        ),
        reference_target_fallback_reason=str(
            reference_target_consumption.get("fallback_reason", "")
        ),
        reference_target_consumption_path=str(paths["reference_target_consumption_path"]),
        selected_skill_pack_id=str(
            latest_skill_pack_invocation.get("selected_skill_pack_id", "")
        ),
        skill_pack_result_state=str(
            latest_skill_pack_result.get("result_state", "")
        ),
        quality_gap_id=str(latest_quality_gap_summary.get("quality_gap_id", "")),
        quality_improvement_state=str(
            latest_quality_improvement_summary.get("improvement_state", "")
        ),
        quality_dimension_id=str(
            latest_quality_improvement_summary.get("quality_dimension_id", "")
        ),
        quality_composite_state=str(
            dict(quality_roadmap_outputs.get("composite_evaluation", {})).get(
                "composite_quality_state",
                "",
            )
        ),
        quality_roadmap_path=str(paths["quality_roadmap_path"]),
        quality_next_pack_plan_path=str(paths["quality_next_pack_plan_path"]),
        skill_pack_invocation_path=str(paths["skill_pack_invocation_path"]),
        skill_pack_result_path=str(paths["skill_pack_result_path"]),
        controller_artifact_path=str(controller_summary_path),
        latest_summary_artifact_path=latest_summary_artifact_path,
    )
    return current_payload
