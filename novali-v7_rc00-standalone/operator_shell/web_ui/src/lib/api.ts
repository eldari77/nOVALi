const API_PREFIX = "/shell/api";

export interface ReviewConfirmationSource {
  review_confirmation_state?: string;
  review_confirmation_label?: string;
  confirmed_outcome_state?: string;
  confirmation_gap_state?: string;
  next_operator_action?: string;
  next_operator_action_label?: string;
  next_operator_action_summary?: string;
  review_confirmed_by?: string;
  review_confirmation_recorded_at?: string;
  valid_explicit_operator_decision_found?: boolean;
  [key: string]: unknown;
}

export interface ReviewDecisionSource {
  decision_source_state?: string;
  decision_source_label?: string;
  decision_source_kind?: string;
  decision_source_path?: string;
  decision_source_valid?: boolean;
  valid_explicit_operator_decision_found?: boolean;
  [key: string]: unknown;
}

export interface PromotionOutcomeConfirmedSource {
  confirmed_outcome_state?: string;
  confirmed_outcome_label?: string;
  decision_source_kind?: string;
  [key: string]: unknown;
}

export interface ConfirmationGapSource {
  confirmation_gap_state?: string;
  confirmation_gap_label?: string;
  exact_missing_confirmation_fields_summary?: string;
  human_action_required?: boolean;
  missing_confirmation_fields?: string[];
  [key: string]: unknown;
}

export interface ReviewSources {
  review_confirmation?: ReviewConfirmationSource;
  review_decision_source?: ReviewDecisionSource;
  promotion_outcome_confirmed?: PromotionOutcomeConfirmedSource;
  confirmation_gap?: ConfirmationGapSource;
  review_decision?: Record<string, unknown>;
}

export interface InterventionQueueItem {
  review_item_id?: string;
  review_id?: string;
  title?: string;
  reason?: string;
  reason_summary?: string;
  action_needed?: string;
  recommended_action?: string;
  severity?: string;
  blocks_continuation?: boolean;
  route?: string;
  [key: string]: unknown;
}

export interface InterventionOption {
  action_id?: string;
  action_kind?: string;
  action_type?: string;
  action_label?: string;
  label?: string;
  description?: string;
  details?: string;
  available?: boolean;
  blocked_reason?: string;
  recommended?: boolean;
  review_item_id?: string;
  route?: string;
  [key: string]: unknown;
}

export interface AttentionInboxItem extends InterventionQueueItem {
  attention_id?: string;
  packet_id?: string;
  bucket?: string;
  action_label?: string;
  actionable_now?: boolean;
  session_id?: string;
  checkpoint_id?: string;
  belongs_to_current_session_lineage?: boolean;
  belongs_to_current_checkpoint_lineage?: boolean;
  lineage_summary?: string;
  [key: string]: unknown;
}

export interface AttentionPacketSummary {
  packet_id?: string;
  label?: string;
  item_count?: number;
  blocking_item_count?: number;
  informational_item_count?: number;
  review_item_ids?: string[];
  batch_safe?: boolean;
  resolvable_now?: boolean;
  resolution_action_id?: string;
  resolution_action_label?: string;
  session_id?: string;
  session_handle?: string;
  workspace_id?: string;
  checkpoint_id?: string;
  packet_summary?: string;
  action_summary?: string;
  remaining_blocking_after_packet?: number;
  remaining_item_count_after_packet?: number;
  remaining_after_packet_summary?: string;
  [key: string]: unknown;
}

export interface AttentionInboxSummary {
  label?: string;
  blocking_count?: number;
  informational_count?: number;
  total_count?: number;
  empty_state_label?: string;
  empty_state_detail?: string;
  blocking_items?: AttentionInboxItem[];
  informational_items?: AttentionInboxItem[];
  current_packet?: AttentionPacketSummary | null;
  [key: string]: unknown;
}

export interface AttentionSignalSummary {
  severity?: string;
  label?: string;
  detail?: string;
  badge_count?: number;
  requires_operator_action?: boolean;
  blocking_count?: number;
  informational_count?: number;
  packet_id?: string;
  [key: string]: unknown;
}

export interface DeltaSinceLastResumeSummary {
  summary_label?: string;
  anchor_checkpoint_id?: string;
  anchor_checkpoint_ordinal?: number;
  checkpoints_added?: number;
  cycles_completed?: number;
  headroom_consumed_materially?: boolean;
  intervention_packet_created?: boolean;
  intervention_packet_resolved?: boolean;
  likely_next_stop_boundary_changed?: boolean;
  current_next_stop_boundary_label?: string;
  same_session_id?: string;
  same_session_preserved?: boolean;
  summary?: string;
  [key: string]: unknown;
}

export interface CampaignHandoffSummary {
  label?: string;
  session_id?: string;
  session_handle?: string;
  lifecycle_state?: string;
  state_label?: string;
  last_checkpoint_id?: string;
  last_checkpoint_at?: string;
  current_cycle?: number;
  max_cycles?: number;
  what_changed_label?: string;
  what_changed_summary?: string;
  latest_progress_marker?: string;
  current_blocker_label?: string;
  current_blocker?: string;
  recommended_next_action_label?: string;
  recommended_next_action_detail?: string;
  next_stop_boundary_label?: string;
  next_stop_boundary_summary?: string;
  policy_headroom_label?: string;
  policy_headroom_summary?: string;
  attention_blocking_count?: number;
  attention_informational_count?: number;
  resume_ready_after_next_action?: boolean;
  resume_ready_after_next_action_summary?: string;
  attention_required?: boolean;
  [key: string]: unknown;
}

export interface ObservabilityStatus {
  enabled?: boolean;
  mode?: "disabled" | "otlp" | "console" | "noop";
  status?: "disabled" | "configured" | "exporting" | "degraded" | "unavailable";
  endpoint_configured?: boolean;
  endpoint_hint?: "localhost" | "host.docker.internal" | "docker_network_alias" | "custom" | "unset";
  service_name?: string;
  service_name_lm_safe?: boolean;
  service_name_lm_warning?: string | null;
  resource_summary?: Record<string, string>;
  last_export_result?: "unknown" | "success" | "failure" | "not_attempted";
  last_error_type?: string | null;
  observability_shutdown?: {
    last_flush_result?:
      | "unknown"
      | "success"
      | "disabled"
      | "unavailable"
      | "timeout"
      | "degraded"
      | "failed";
    last_shutdown_result?:
      | "unknown"
      | "success"
      | "disabled"
      | "unavailable"
      | "timeout"
      | "degraded"
      | "failed";
    last_timeout_count?: number;
    last_error_type?: string | null;
    last_error_summary_redacted?: string | null;
    last_shutdown_time?: string | null;
    timeout_ms?: number;
    traceback_suppressed_for_expected_timeout?: boolean;
    unexpected_exception_seen?: boolean;
    [key: string]: unknown;
  };
  last_otel_shutdown_result?:
    | "unknown"
    | "success"
    | "disabled"
    | "unavailable"
    | "timeout"
    | "degraded"
    | "failed";
  last_otel_shutdown_timeout_count?: number;
  last_otel_shutdown_error_type?: string | null;
  expected_timeout_traceback_suppressed?: boolean;
  redaction_mode?: "strict" | "standard";
  active_otlp_protocol?: "http" | "grpc" | "unknown";
  lm_mapping_attributes_complete?: boolean;
  lm_mapping_missing?: string[];
  export_failure_count?: number;
  live_collector_probe?: {
    enabled?: boolean;
    last_probe_result?: "unknown" | "success" | "failure" | "skipped";
    last_probe_kind?: string | null;
    last_probe_id?: string | null;
    last_probe_time?: string | null;
    endpoint_hint?: "localhost" | "host.docker.internal" | "docker_network_alias" | "custom" | "unset";
    collector_mode?: "unknown" | "docker" | "same_host" | "custom";
    no_secrets_captured?: boolean;
    [key: string]: unknown;
  };
  trace_visibility_probe?: {
    enabled?: boolean;
    last_probe_result?: "unknown" | "success" | "failure" | "skipped" | "not_recorded";
    last_probe_id?: string | null;
    last_probe_time?: string | null;
    endpoint_hint?: "localhost" | "host.docker.internal" | "docker_network_alias" | "custom" | "unset";
    otlp_protocol?: "http" | "grpc" | "unknown";
    service_name?: string;
    service_name_lm_safe?: boolean;
    lm_mapping_attributes_complete?: boolean;
    lm_mapping_missing?: string[];
    no_secrets_captured?: boolean;
    [key: string]: unknown;
  };
  dockerized_agent_probe?: {
    enabled?: boolean;
    last_probe_result?: "unknown" | "success" | "failure" | "skipped" | "not_recorded";
    last_probe_id?: string | null;
    last_probe_time?: string | null;
    endpoint_hint?: "localhost" | "host.docker.internal" | "docker_network_alias" | "custom" | "unset";
    endpoint_mode?: "same_network" | "host_gateway" | "host_published" | "custom" | "unknown";
    network_mode?: "same_network" | "host_gateway" | "host_published" | "custom" | "unknown";
    otlp_protocol?: "http" | "grpc" | "unknown";
    service_name?: string;
    service_name_lm_safe?: boolean;
    lm_mapping_attributes_complete?: boolean;
    lm_mapping_missing?: string[];
    container_runtime_proven?: boolean;
    container_hostname?: string | null;
    no_secrets_captured?: boolean;
    [key: string]: unknown;
  };
  last_visibility_probe_result?: "unknown" | "success" | "failure" | "skipped" | "not_recorded";
  last_visibility_probe_id?: string | null;
  dockerized_agent_probe_result?: "unknown" | "success" | "failure" | "skipped" | "not_recorded";
  dockerized_agent_probe_id?: string | null;
  dockerized_agent_runtime_proven?: boolean;
  dockerized_endpoint_mode?: "same_network" | "host_gateway" | "host_published" | "custom" | "unknown";
  dockerized_network_mode?: "same_network" | "host_gateway" | "host_published" | "custom" | "unknown";
  dockerized_protocol?: "http" | "grpc" | "unknown";
  dockerized_mapping_complete?: boolean;
  last_portal_confirmation?: "confirmed" | "not_confirmed" | "not_recorded";
  portal_confirmation?: {
    confirmation_state?: "confirmed" | "not_confirmed" | "not_recorded";
    proof_id?: string | null;
    service_name?: string | null;
    recorded_at?: string | null;
    protocol?: string | null;
    endpoint_mode?: string | null;
    confirmation_source?: string | null;
    [key: string]: unknown;
  };
  alert_candidates?: Array<{
    alert_key?: string;
    label?: string;
    severity?: string;
    detail?: string;
    state?: string;
    [key: string]: unknown;
  }>;
  [key: string]: unknown;
}

export interface ExternalAdapterStatus {
  enabled?: boolean;
  mode?: "disabled" | "mock_only";
  status?: "disabled" | "ready" | "review_required" | "failed" | "kill_switch_triggered";
  adapter_name?: string;
  adapter_kind?: string;
  schema_version?: string;
  last_proof_result?: "unknown" | "success" | "failure" | "skipped";
  last_action_status?: string | null;
  last_review_required?: boolean;
  review_reasons?: string[];
  last_replay_packet_id?: string | null;
  replay_packet_count?: number;
  kill_switch_state?: "inactive" | "triggered";
  telemetry_enabled?: boolean;
  lm_portal_trace_confirmation?: "operator_confirmed" | "not_confirmed" | "not_recorded";
  last_review_item_id?: string | null;
  last_rollback_analysis_id?: string | null;
  [key: string]: unknown;
}

export interface ExternalAdapterReviewItemSummary {
  review_item_id?: string;
  action_type?: string;
  action_status?: string;
  review_status?: string;
  severity?: string;
  review_reasons?: string[];
  operator_action_required?: string;
  replay_packet_id?: string | null;
  rollback_analysis_id?: string | null;
  checkpoint_ref?: string | null;
  evidence_integrity_status?: string;
  [key: string]: unknown;
}

export interface ExternalAdapterReviewStatus {
  enabled?: boolean;
  mode?: "mock_only" | "disabled";
  status?: "clear" | "pending_review" | "escalated" | "blocked";
  pending_count?: number;
  escalated_count?: number;
  evidence_missing_count?: number;
  last_review_item_id?: string | null;
  last_replay_packet_id?: string | null;
  last_rollback_analysis_id?: string | null;
  last_operator_action_required?: string | null;
  last_checkpoint_ref?: string | null;
  rollback_possible?: boolean;
  rollback_candidate?: boolean;
  checkpoint_available?: boolean;
  restore_allowed?: boolean;
  restore_performed?: boolean;
  ambiguity_level?: string;
  review_items?: ExternalAdapterReviewItemSummary[];
  advisory_copy?: string[];
  [key: string]: unknown;
}

export interface ControllerIsolationLaneSummary {
  lane_id?: string;
  lane_role?: string;
  active?: boolean;
  mode?: "mock_only";
  adoption_authority?: boolean;
  coordination_authority?: boolean;
  doctrine_namespace?: string;
  memory_namespace?: string;
  summary_namespace?: string;
  intervention_namespace?: string;
  replay_namespace?: string;
  review_namespace?: string;
  [key: string]: unknown;
}

export interface ControllerIsolationReviewTicket {
  review_ticket_id?: string;
  finding_id?: string;
  finding_type?: string;
  lane_id?: string;
  source_lane_id?: string;
  target_lane_id?: string | null;
  review_status?: string;
  severity?: string;
  operator_action_required?: string;
  review_reasons?: string[];
  replay_packet_id?: string | null;
  [key: string]: unknown;
}

export interface ControllerIsolationStatus {
  enabled?: boolean;
  mode?: "disabled" | "mock_only";
  status?: "disabled" | "ready" | "review_required" | "review_blocked" | "failed";
  schema_version?: string;
  lanes?: ControllerIsolationLaneSummary[];
  lane_count?: number;
  isolation_checks?: {
    namespace_separation?: "pass" | "warning" | "fail";
    no_hidden_shared_scratchpad?: "pass" | "warning" | "fail";
    director_channel_required?: "pass" | "warning" | "fail";
    telemetry_lane_identity?: "pass" | "warning" | "fail";
    [key: string]: unknown;
  };
  identity_bleed?: {
    finding_count?: number;
    high_count?: number;
    critical_count?: number;
    latest_finding_id?: string | null;
    latest_review_ticket_id?: string | null;
    [key: string]: unknown;
  };
  cross_lane_messages?: {
    proposed_count?: number;
    approved_count?: number;
    blocked_count?: number;
    unauthorized_count?: number;
    latest_message_id?: string | null;
    [key: string]: unknown;
  };
  last_proof_result?: "unknown" | "success" | "failure";
  latest_review_ticket_id?: string | null;
  latest_replay_packet_id?: string | null;
  review_tickets?: ControllerIsolationReviewTicket[];
  lm_portal_trace_confirmation?: "operator_confirmed" | "not_confirmed" | "not_recorded";
  advisory_copy?: string[];
  [key: string]: unknown;
}

export interface ReadOnlyAdapterReviewTicket {
  review_item_id?: string;
  action_type?: string;
  action_status?: string;
  review_status?: string;
  severity?: string;
  review_reasons?: string[];
  operator_action_required?: string;
  replay_packet_id?: string | null;
  rollback_analysis_id?: string | null;
  [key: string]: unknown;
}

export interface ReadOnlyAdapterStatus {
  enabled?: boolean;
  mode?: "disabled" | "fixture_read_only";
  status?: "disabled" | "ready" | "observed" | "review_required" | "review_blocked" | "failed";
  schema_version?: string;
  adapter_name?: string;
  adapter_kind?: string;
  source_kind?: string;
  environment_kind?: string;
  latest_snapshot_id?: string | null;
  latest_replay_packet_id?: string | null;
  latest_review_ticket_id?: string | null;
  latest_rollback_analysis_id?: string | null;
  latest_mutation_refusal_id?: string | null;
  validation_status?: "unknown" | "clean" | "warning" | "failed" | "review_required";
  integrity_status?: "unknown" | "clean" | "warning" | "failed" | "review_required";
  review_required?: boolean;
  review_reasons?: string[];
  mutation_allowed?: false;
  mutation_refused_count?: number;
  observation_count?: number;
  bad_snapshot_count?: number;
  stale_snapshot_count?: number;
  conflicting_observation_count?: number;
  lane_id?: string | null;
  lane_attribution_status?: "unknown" | "valid" | "wrong_lane" | "review_required";
  lm_portal_trace_confirmation?: "operator_confirmed" | "not_confirmed" | "not_recorded";
  review_tickets?: ReadOnlyAdapterReviewTicket[];
  advisory_copy?: string[];
  [key: string]: unknown;
}

export interface OperatorAlertSummaryItem {
  alert_id?: string;
  alert_type?: string;
  severity?: string;
  status?: string;
  title?: string;
  summary_redacted?: string;
  operator_action_required?: string;
  evidence_bundle_id?: string;
  acknowledged_at?: string | null;
  reviewed_at?: string | null;
  [key: string]: unknown;
}

export interface OperatorAlertActionSummary {
  action_id?: string;
  label?: string;
  alert_id?: string;
  [key: string]: unknown;
}

export interface OperatorAlertsStatus {
  enabled?: boolean;
  mode?: "local_evidence_only";
  status?:
    | "clear"
    | "raised"
    | "acknowledged"
    | "reviewed"
    | "blocked_waiting_operator"
    | "failed";
  schema_version?: string;
  alert_count?: number;
  raised_count?: number;
  acknowledged_count?: number;
  reviewed_count?: number;
  blocked_count?: number;
  critical_count?: number;
  high_count?: number;
  warning_count?: number;
  latest_alert_id?: string | null;
  latest_alert_type?: string | null;
  latest_evidence_bundle_id?: string | null;
  latest_operator_action_required?: string | null;
  read_only_alert_count?: number;
  telemetry_alert_candidate_count?: number;
  telemetry_shutdown_alert_count?: number;
  latest_telemetry_shutdown_alert_id?: string | null;
  identity_bleed_alert_count?: number;
  lm_portal_trace_confirmation?: "operator_confirmed" | "not_confirmed" | "not_recorded";
  alerts?: OperatorAlertSummaryItem[];
  available_actions?: OperatorAlertActionSummary[];
  advisory_copy?: string[];
  [key: string]: unknown;
}

export interface OperatorState {
  schema_name: string;
  generated_at: string;
  operator_state: {
    no_directive_loaded?: boolean;
    directive_loaded?: boolean;
    bootstrap_ready?: boolean;
    bootstrap_running?: boolean;
    governed_ready?: boolean;
    governed_running?: boolean;
    review_required?: boolean;
    intervention_required?: boolean;
    resumable_session_present?: boolean;
    awaiting_operator_confirmation?: boolean;
    paused?: boolean;
    halted?: boolean;
    completed?: boolean;
    error?: boolean;
  };
  directive: {
    path: string;
    summary: string;
    is_valid: boolean;
    details?: string[];
  };
  directive_candidates: Array<{ path: string; label: string }>;
  runtime: {
    execution_profile: string;
    run_status: string;
    stop_reason: string;
    workflow_stage: string;
  };
  session: {
    session_state: string;
    session_label: string;
    run_status: string;
    stop_reason: string;
    workflow_stage: string;
    execution_profile: string;
    next_action: string;
    next_action_detail: string;
  };
  launch_readiness: {
    bootstrap: LaunchReadiness;
    governed: LaunchReadiness;
  };
  intervention: {
    required: boolean;
    summary: string;
    reason: string;
    recommended_action: string;
    recommended_action_detail: string;
    queue_items: InterventionQueueItem[];
    options: InterventionOption[];
    pending_review_count: number;
    blocking_review_count: number;
    total_review_item_count?: number;
    review_required_state: string;
    review_workspace_label?: string;
    next_state_after_review: string;
    primary_reason_class?: string;
    current_primary_review_item_id?: string;
    current_primary_review_title?: string;
    resolved_review_item_id?: string;
    resolved_review_item_ids?: string[];
    resolved_review_item_count?: number;
    latest_decision_action_label?: string;
    latest_resolution_state?: string;
    latest_resolution_summary?: string;
    latest_resolution_generated_at?: string;
  };
  review_sources: ReviewSources;
  external_adapter?: ExternalAdapterStatus;
  external_adapter_review?: ExternalAdapterReviewStatus;
  controller_isolation?: ControllerIsolationStatus;
  read_only_adapter?: ReadOnlyAdapterStatus;
  operator_alerts?: OperatorAlertsStatus;
  artifacts: {
    runtime_event_log_path: string;
    workspace_root: string;
    workspace_id: string;
    output_artifact_paths: string[];
    latest_artifact_index_path: string;
    session_artifact_path: string;
  };
  observability?: ObservabilityStatus;
}

export interface LongRunEffectivePolicy {
  continuation_strategy?: string;
  continuation_strategy_label?: string;
  governed_execution_mode?: string;
  max_total_cycles?: number;
  max_cycles_per_invocation?: number;
  current_cycle?: number;
  cycles_remaining?: number;
  checkpoint_count?: number;
  latest_checkpoint_id?: string;
  latest_checkpoint_at?: string;
  restart_attempt_count?: number;
  max_restart_attempts?: number;
  remaining_restart_attempts?: number;
  supervisor_enabled?: boolean;
  supervisor_enabled_read_only?: boolean;
  editable_fields?: string[];
  read_only_fields?: string[];
  read_only_notes?: Record<string, string>;
  apply_scope_summary?: string;
  stop_boundary_summary?: string;
}

export interface LongRunStatePayload {
  schema_name: string;
  generated_at: string;
  long_run: {
    schema_name: string;
    schema_version: string;
    session_id: string;
    workspace_id: string;
    workspace_root: string;
    lifecycle_state: string;
    checkpoint_count: number;
    current_cycle: number;
    max_cycles: number;
    max_cycles_per_invocation?: number;
    last_checkpoint_at?: string;
    last_progress_at?: string;
    supervisor_enabled?: boolean;
    active_invocation_id?: string;
    lease_owner_id?: string;
    lease_acquired_at?: string;
    lease_expires_at?: string;
    lease_state?: string;
    stale_recovery_available?: boolean;
    next_eligible_at?: string;
    last_heartbeat_at?: string;
    duplicate_launch_blocked?: boolean;
    duplicate_launch_reason?: string;
    operator_pause_requested?: boolean;
    operator_stop_requested?: boolean;
    resume_available: boolean;
    resume_blocked?: boolean;
    resume_blocked_reason?: string;
    resume_from_checkpoint_id?: string;
    latest_checkpoint_id?: string;
    latest_checkpoint_path?: string;
    budget_remaining?: {
      elapsed_seconds?: number;
      remaining_cycles?: number;
      remaining_wall_clock_seconds?: number;
      remaining_restart_attempts?: number;
      remaining_tool_calls?: number;
      remaining_trusted_source_calls?: number;
    };
    halt_reason?: string;
    completion_state?: string;
    active_process_id?: number;
    watchdog_state?: string;
    operator_summary?: string;
    recommended_next_action?: string;
    latest_checkpoint?: {
      checkpoint_id?: string;
      checkpoint_path?: string;
      generated_at?: string;
      checkpoint_count?: number;
      current_cycle?: number;
    };
    checkpoint_inventory_path?: string;
  };
  effective_policy?: LongRunEffectivePolicy;
  operator_guidance: {
    session_handle: string;
    state_family: string;
    state_label: string;
    blocking_reason: string;
    headroom_summary: string;
    settings_summary: string;
    same_session_summary: string;
    attention_signal?: AttentionSignalSummary;
    campaign_handoff_summary?: CampaignHandoffSummary;
    delta_since_last_resume?: DeltaSinceLastResumeSummary;
    next_stop_boundary_label?: string;
    next_stop_boundary_summary?: string;
    controls_location: string;
    current_execution_profile: string;
    expected_execution_profile: string;
    workspace_materialized: boolean;
    review_gate_active: boolean;
    blocking_review_count: number;
    pending_review_count: number;
    attention_inbox?: AttentionInboxSummary;
    intervention_guidance?: {
      active?: boolean;
      workspace_state?: string;
      workspace_label?: string;
      summary?: string;
      primary_review_item_id?: string;
      primary_title?: string;
      primary_reason_class?: string;
      primary_reason_summary?: string;
      resolved_review_item_count?: number;
      total_review_item_count?: number;
      remaining_review_item_count?: number;
      remaining_blocking_review_count?: number;
      latest_resolution_state?: string;
      latest_resolution_summary?: string;
      resume_ready_after_review_clear?: boolean;
      resume_ready_after_review_clear_detail?: string;
      review_progress_summary?: string;
    };
    primary_cta: {
      action_id: string;
      label: string;
      detail: string;
      available: boolean;
      target?: string;
      tone?: string;
      blocked_reason?: string;
      preferred_review_action_id?: string;
      preferred_review_item_id?: string;
      attention_packet_id?: string;
    };
    secondary_controls?: Array<{
      action_id: string;
      label: string;
      detail: string;
      available: boolean;
      blocked_reason?: string;
      tone?: string;
    }>;
    effective_policy?: LongRunEffectivePolicy;
  };
  operator_state: OperatorState["operator_state"];
  intervention: Record<string, unknown>;
  session: OperatorState["session"];
}

export interface LaunchReadiness {
  can_launch: boolean;
  selected_launch: string;
  workflow_lane: string;
  selected_execution_profile: string;
  expected_execution_profile: string;
  profile_matches_selected_action: boolean;
  operator_next_action: string;
  operator_next_action_detail: string;
  blocking_reasons: string[];
  warnings: string[];
}

export interface LaunchStatusPayload {
  schema_name: string;
  generated_at: string;
  mode: string;
  operator_next_action: string;
  operator_next_action_detail: string;
  can_launch: boolean;
  selected_launch: string;
  workflow_lane: string;
  expected_execution_profile: string;
  blocking_reasons: string[];
  warnings: string[];
  operator_state: OperatorState["operator_state"];
}

export type LaunchStatusSnapshot = LaunchReadiness | LaunchStatusPayload;

export interface ReviewPayload {
  schema_name?: string;
  generated_at: string;
  intervention_required: boolean;
  review_required: boolean;
  intervention: OperatorState["intervention"];
  attention_inbox?: AttentionInboxSummary;
  review_source: ReviewSources;
  operator_state: OperatorState["operator_state"];
  session: OperatorState["session"];
}

export interface RuntimeEventPayload {
  schema_name?: string;
  generated_at?: string;
  timestamp: string;
  event_type: string;
  phase: string;
  message: string;
  workspace_id: string;
  session_id: string;
  artifact_path: string;
  directive_id: string;
}

type JsonBody = Record<string, unknown>;

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  return fetch(`${API_PREFIX}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    credentials: "include",
  }).then((response) => parseJsonResponse<T>(response));
}

async function requestJsonBody<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_PREFIX}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    credentials: "include",
  });
  const text = await response.text();
  let json: Record<string, unknown> = {};
  try {
    json = JSON.parse(text || "{}") as Record<string, unknown>;
  } catch {
    json = {};
  }
  if (!response.ok) {
    const details = Array.isArray(json.details)
      ? json.details.map((item) => String(item || "").trim()).filter(Boolean)
      : [];
    const message =
      String(json.headline || json.message || "").trim() ||
      text ||
      `Request failed: ${response.status}`;
    throw new Error([message, ...details].filter(Boolean).join(" "));
  }
  return json as T;
}

function requestForm<T>(path: string, body: FormData, options: Omit<RequestInit, "body"> = {}): Promise<T> {
  return fetch(`${API_PREFIX}${path}`, {
    method: "POST",
    body,
    credentials: "include",
    ...options,
  }).then((response) => parseJsonResponse<T>(response));
}

export function fetchOperatorState(): Promise<OperatorState> {
  return request<OperatorState>("/operator-state");
}

export function fetchBootstrapStatus(): Promise<LaunchStatusPayload> {
  return request<LaunchStatusPayload>("/bootstrap/status");
}

export function fetchGovernedStatus(): Promise<LaunchStatusPayload> {
  return request<LaunchStatusPayload>("/governed/status");
}

export function fetchInterventionState(): Promise<ReviewPayload> {
  return request<ReviewPayload>("/intervention-state");
}

export function fetchLongRunState(): Promise<LongRunStatePayload> {
  return request<LongRunStatePayload>("/long-run-state");
}

export function pauseLongRun(): Promise<JsonBody> {
  return request("/long-run/pause", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function resumeLongRun(): Promise<JsonBody> {
  return request("/long-run/resume", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function continueLongRun(): Promise<JsonBody> {
  return request("/long-run/continue", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function saveLongRunPolicy(payload: {
  continuation_strategy: string;
  max_total_cycles: string;
  max_cycles_per_invocation: string;
}): Promise<{
  ok: boolean;
  headline?: string;
  message?: string;
  details?: string[];
  effective_policy?: LongRunEffectivePolicy;
  state?: LongRunStatePayload;
}> {
  return requestJsonBody("/long-run/policy", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function executeReviewAction(payload: {
  action_id: string;
  review_item_id?: string;
  operator_note?: string;
}): Promise<JsonBody> {
  return request("/review/action", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function executeOperatorAlertAction(payload: {
  action_id: string;
  alert_id: string;
  operator_note?: string;
  replacement_alert_id?: string;
}): Promise<JsonBody> {
  return request("/operator-alerts/action", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function stopLongRun(): Promise<JsonBody> {
  return request("/long-run/stop", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function selectDirective(directivePath: string): Promise<{ ok: boolean; message: string; state?: OperatorState }> {
  return request("/directive/select", {
    method: "POST",
    body: JSON.stringify({ directive_path: directivePath }),
  });
}

export function uploadDirective(payload: { directive_upload: File }): Promise<{ ok: boolean; message: string; path: string }> {
  const formData = new FormData();
  formData.append("directive_upload", payload.directive_upload);
  return requestForm("/directive/upload", formData);
}

export function validateTrustedSource(payload: JsonBody): Promise<JsonBody> {
  return request("/trusted-source/validate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function startBootstrap(payload: JsonBody): Promise<JsonBody> {
  return request("/bootstrap/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function prepareGovernedExecution(payload: JsonBody): Promise<JsonBody> {
  return request("/governed/prepare", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function startGoverned(payload: JsonBody): Promise<JsonBody> {
  return request("/governed/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function openRuntimeEventStream(
  handler: {
    onOpen?: () => void;
    onEvent: (event: RuntimeEventPayload) => void;
    onHeartbeat: (event: { generated_at: string }) => void;
    onError?: (error: Event) => void;
  },
): () => void {
  const source = new EventSource(`${API_PREFIX}/runtime-events`);
  source.onopen = () => {
    handler.onOpen?.();
  };
  source.addEventListener("runtime_event", (event) => {
    try {
      const data = JSON.parse(String((event as MessageEvent).data || "{}")) as RuntimeEventPayload;
      handler.onEvent(data);
    } catch {
      /* preserve stream even if payload is malformed */
    }
  });
  source.addEventListener("heartbeat", (event) => {
    try {
      const data = JSON.parse(String((event as MessageEvent).data || "{}")) as {
        generated_at: string;
      };
      handler.onHeartbeat(data);
    } catch {
      handler.onHeartbeat({ generated_at: "" });
    }
  });
  source.onerror = (event) => {
    handler.onError?.(event as Event);
  };
  return () => source.close();
}
