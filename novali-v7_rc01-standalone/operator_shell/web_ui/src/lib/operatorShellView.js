export const OPERATOR_ARCANE_THEME = {
  mode: "dark_console",
  accentPolicy: "emerald-purple-silver",
  colors: {
    console: "#090812",
    panel: "#12111f",
    elevated: "#181529",
    darkPurple: "#2b1746",
    purpleMist: "#7c5aa6",
    emerald: "#34d399",
    emeraldDeep: "#0f8b68",
    silver: "#c8ced8",
    silverDim: "#87909f",
    warning: "#d8a657",
    danger: "#ef5f6c",
  },
};

const asRecord = (value) => (value && typeof value === "object" ? value : {});
const asArray = (value) => (Array.isArray(value) ? value : []);
const text = (...values) => {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    const next = String(value).trim();
    if (next) return next;
  }
  return "";
};
const numberValue = (value, fallback = 0) => {
  const next = Number(value);
  return Number.isFinite(next) ? next : fallback;
};

export function buildCommandOverview({ longRun, autonomy, observability, operatorState } = {}) {
  const longRunPayload = asRecord(asRecord(longRun).long_run || longRun);
  const guidance = asRecord(asRecord(longRun).operator_guidance);
  const autonomyPayload = asRecord(autonomy);
  const memory = asRecord(autonomyPayload.memory_pressure);
  const operator = asRecord(operatorState);
  const primaryCta = asRecord(guidance.primary_cta);
  const staleRecovery = Boolean(longRunPayload.stale_recovery_available);
  const emergencyStop = Boolean(autonomyPayload.emergency_stop_enabled || autonomyPayload.emergency_stop);
  const reviewRequired = Boolean(
    operator.review_required ||
      operator.intervention_required ||
      longRunPayload.intervention_required,
  );
  const readyToContinue = Boolean(
    longRunPayload.next_continuation_ready ||
      longRunPayload.bounded_continuation_handoff ||
      longRunPayload.resume_available,
  );
  const oomState = text(memory.oom_guard_state, longRunPayload.oom_guard_state, "normal");
  const memoryState = text(
    memory.memory_smoothing_state,
    longRunPayload.memory_smoothing_state,
    "normal",
  );
  let safetyTone = "healthy";
  if (emergencyStop || oomState === "recycle_required" || oomState === "hibernate_required") {
    safetyTone = "danger";
  } else if (staleRecovery || reviewRequired || memoryState === "cooling" || memoryState === "spilling") {
    safetyTone = "attention";
  }
  const headline = emergencyStop
    ? "Emergency stop active"
    : staleRecovery
      ? "Recovery attention needed"
      : reviewRequired
        ? "Operator review needed"
        : readyToContinue
          ? "Ready to continue"
          : text(guidance.state_family, longRunPayload.lifecycle_state, "Monitoring");
  const primaryAction = {
    id: text(primaryCta.action_id, readyToContinue ? "continue" : "review"),
    label: text(primaryCta.label, readyToContinue ? "Continue session" : "Review state"),
    enabled: !emergencyStop && !staleRecovery,
  };
  return {
    headline,
    safetyTone,
    stateFamily: text(guidance.state_family, longRunPayload.lifecycle_state, "unknown"),
    runtimeState: text(autonomyPayload.runtime_state, "unknown"),
    lifecycle: text(longRunPayload.lifecycle_state, "unknown"),
    leaseState: text(longRunPayload.lease_state, "unknown"),
    checkpointCount: numberValue(longRunPayload.checkpoint_count),
    staleRecovery,
    memoryState,
    oomState,
    observabilityState: text(asRecord(observability).status, asRecord(observability).otel_status, "unknown"),
    nextAction: text(
      longRunPayload.recommended_next_action,
      guidance.recommended_next_action,
      "Inspect the next safe operator action.",
    ),
    primaryAction,
  };
}

const normalizeQueueItem = (item, bucket) => ({
  id: text(item.review_item_id, item.review_id, item.session_id, item.session_handle, item.title, bucket),
  title: text(item.title, item.session_handle, item.queue_bucket_label, "Untitled item"),
  detail: text(
    item.reason_summary,
    item.reason,
    item.current_blocker,
    item.blocker,
    item.shortcut_action_detail,
    "No detail recorded.",
  ),
  actionLabel: text(item.action_label, item.shortcut_action_label, item.recommended_action, "Inspect summary"),
  severity: text(item.severity, item.queue_bucket_label, bucket),
  bucket,
  raw: item,
});

export function buildAttentionQueue({ operatorState } = {}) {
  const operator = asRecord(operatorState);
  const intervention = asRecord(operator.intervention);
  const portfolio = asRecord(operator.session_portfolio || operator.portfolio);
  const reviewItems = asArray(intervention.queue_items).map((item) => asRecord(item));
  const portfolioCards = asArray(portfolio.cards || portfolio.items || operator.session_portfolio_cards).map((item) =>
    asRecord(item),
  );
  const blockers = [
    ...reviewItems.filter((item) => Boolean(item.blocks_continuation || item.severity === "critical")),
    ...portfolioCards.filter((item) => /blocking|review|intervention/i.test(text(item.queue_bucket_label))),
  ].map((item) => normalizeQueueItem(item, "blocker"));
  const resumable = portfolioCards
    .filter((item) => /resumable|continue|handoff/i.test(text(item.queue_bucket_label, item.shortcut_action_label)))
    .map((item) => normalizeQueueItem(item, "resumable"));
  const informational = [
    ...reviewItems.filter((item) => !Boolean(item.blocks_continuation || item.severity === "critical")),
    ...portfolioCards.filter((item) => /informational|recent|history/i.test(text(item.queue_bucket_label))),
  ].map((item) => normalizeQueueItem(item, "informational"));
  return {
    blockers,
    resumable,
    informational,
    totalCount: blockers.length + resumable.length + informational.length,
  };
}

export function buildDirectiveWorkSummary({ autonomy, currentDirective, longRun, operatorState } = {}) {
  const autonomyPayload = asRecord(autonomy);
  const directivePayload = asRecord(currentDirective);
  const directiveTrackProgress = asRecord(directivePayload.latest_directive_track_progress);
  const longRunPayload = asRecord(asRecord(longRun).long_run || longRun);
  const intervention = asRecord(asRecord(longRun).intervention || asRecord(operatorState).intervention);
  const meaningful = asRecord(autonomyPayload.latest_meaningful_work || autonomyPayload.meaningful_work);
  const latest = asRecord(
    autonomyPayload.latest_operation_result ||
      autonomyPayload.latest_result ||
      meaningful.latest_operation_result,
  );
  const dossierMaterialDelta = Boolean(
    latest.directive_dossier_materially_new ||
      meaningful.directive_dossier_materially_new ||
      directiveTrackProgress.directive_dossier_materially_new,
  );
  const dossierCredited = Boolean(meaningful.directive_dossier_delta_credited);
  const latestDossierRef = text(
    latest.directive_dossier_artifact_relative_path,
    latest.latest_directive_dossier_ref,
    meaningful.latest_directive_dossier_ref,
    meaningful.directive_dossier_artifact_relative_path,
    directiveTrackProgress.latest_directive_dossier_ref,
    directiveTrackProgress.directive_dossier_artifact_relative_path,
    "",
  );
  const deliverableKind = text(
    latest.selected_deliverable_kind,
    meaningful.directive_track_deliverable_kind,
    meaningful.selected_deliverable_kind,
    directiveTrackProgress.selected_deliverable_kind,
    directiveTrackProgress.deliverable_kind,
    "not_recorded",
  );
  const trackMaterialDelta = Boolean(
    latest.delta_materially_new ??
      meaningful.directive_track_delta_materially_new ??
      directiveTrackProgress.delta_materially_new,
  );
  const trackCredited = Boolean(meaningful.directive_track_delta_credited);
  const trackRejectionReason = text(
    latest.delta_rejection_reason,
    meaningful.directive_track_delta_rejection_reason,
    directiveTrackProgress.delta_rejection_reason,
    "none",
  );
  const dossierRejectionReason = text(
    latest.directive_dossier_rejection_reason,
    meaningful.directive_dossier_rejection_reason,
    directiveTrackProgress.directive_dossier_rejection_reason,
    "none",
  );
  const meaningfulDelta = Boolean(
    meaningful.meaningful_delta ||
      dossierCredited ||
      dossierMaterialDelta ||
      trackCredited ||
      trackMaterialDelta,
  );
  const meaningfulCreditKind =
    meaningfulDelta && (dossierCredited || dossierMaterialDelta)
      ? "directive_dossier"
      : meaningfulDelta && (trackCredited || trackMaterialDelta)
        ? "directive_track"
        : "none";
  const meaningfulCreditLabel =
    meaningfulCreditKind === "directive_dossier"
      ? "Dossier delta credited"
      : meaningfulCreditKind === "directive_track"
        ? "Track delta credited"
        : "No credited delta";
  const meaningfulRejectionReason =
    meaningfulCreditKind === "directive_dossier" ? dossierRejectionReason : trackRejectionReason;
  const interventionRequired = Boolean(
    intervention.required ||
      longRunPayload.intervention_required ||
      asRecord(operatorState).intervention_required,
  );
  const staleRecovery = Boolean(longRunPayload.stale_recovery_available);
  const readyToContinue = Boolean(
    longRunPayload.next_continuation_ready ||
      longRunPayload.bounded_continuation_handoff ||
      longRunPayload.resume_available,
  );
  const executionGate = interventionRequired
    ? "Operator review required"
    : staleRecovery
      ? "Stale recovery review required"
      : readyToContinue
        ? "No operator review gate blocking continuation"
        : "No active gate recorded";
  return {
    directiveLoaded: Boolean(directivePayload.directive_selected || directivePayload.directive_id),
    directiveId: text(directivePayload.directive_id, directivePayload.id, "loaded directive"),
    directiveTitle: text(directivePayload.directive_title, directivePayload.title, "Loaded directive"),
    directiveSummary: text(
      directivePayload.directive_summary,
      directivePayload.clarified_intent_summary,
      directivePayload.summary,
      "No directive summary exposed.",
    ),
    directiveStatus: text(
      directivePayload.session_state_label,
      directivePayload.session_state,
      directivePayload.recommended_resume_mode,
      "status unknown",
    ),
    directiveFileStatus: text(
      directivePayload.session_state_label,
      directivePayload.session_state,
      "status unknown",
    ),
    executionGate,
    score: numberValue(
      meaningful.score,
      numberValue(meaningful.meaningful_work_score, numberValue(autonomyPayload.meaningful_work_score, 0)),
    ),
    meaningfulDelta,
    meaningfulCreditKind,
    meaningfulCreditLabel,
    meaningfulRejectionReason,
    deltaCredited: trackCredited,
    dossierCredited,
    dossierState: text(
      latest.directive_work_program_state,
      meaningful.directive_work_program_state,
      directiveTrackProgress.directive_work_program_state,
      "not_recorded",
    ),
    dossierRequired: Boolean(
      latest.directive_dossier_required ??
        meaningful.directive_dossier_required ??
        directiveTrackProgress.directive_dossier_required,
    ),
    dossierMaterialDelta,
    latestDossierRef,
    dossierSignature: text(
      latest.directive_dossier_signature,
      meaningful.directive_dossier_signature,
      directiveTrackProgress.directive_dossier_signature,
      "",
    ),
    dossierRejectionReason,
    sourceCoverageState: text(
      latest.directive_source_coverage_state,
      meaningful.directive_source_coverage_state,
      directiveTrackProgress.directive_source_coverage_state,
      "not_recorded",
    ),
    librarianGapReuseDecision: text(
      latest.librarian_gap_reuse_decision,
      meaningful.librarian_gap_reuse_decision,
      directiveTrackProgress.librarian_gap_reuse_decision,
      "not_recorded",
    ),
    trustedSourceRetrievalValidationState: text(
      latest.trusted_source_retrieval_validation_state,
      meaningful.trusted_source_retrieval_validation_state,
      directiveTrackProgress.trusted_source_retrieval_validation_state,
      "not_recorded",
    ),
    weakArea: text(asArray(meaningful.weak_areas)[0], meaningful.weak_area, "none"),
    deltaSignature: text(meaningful.directive_track_delta_signature, meaningful.new_information_delta_signature, ""),
    progressGeneratedAt: text(
      meaningful.directive_track_progress_generated_at,
      directiveTrackProgress.generated_at,
      "",
    ),
    depthIteration: numberValue(
      latest.depth_iteration,
      numberValue(meaningful.directive_track_depth_iteration, numberValue(directiveTrackProgress.depth_iteration, 0)),
    ),
    materialDelta: trackMaterialDelta,
    deliverableKind,
    artifactDepth: text(
      latest.artifact_depth,
      meaningful.directive_track_artifact_depth,
      meaningful.artifact_depth,
      directiveTrackProgress.artifact_depth,
      "unknown",
    ),
    focusId: text(
      latest.delta_focus_id,
      meaningful.directive_track_delta_focus_id,
      meaningful.delta_focus_id,
      directiveTrackProgress.delta_focus_id,
      "none",
    ),
    layerId: text(
      latest.delta_layer_id,
      meaningful.directive_track_delta_layer_id,
      meaningful.delta_layer_id,
      directiveTrackProgress.delta_layer_id,
      "none",
    ),
    rejectionReason: trackRejectionReason,
    promotionState: text(autonomyPayload.promotion_packet_state, meaningful.promotion_packet_state, "unknown"),
    artifactPath: text(
      latest.directive_track_artifact_relative_path,
      meaningful.directive_track_artifact_relative_path,
      meaningful.directive_track_artifact_ref,
      directiveTrackProgress.directive_track_artifact_relative_path,
      directiveTrackProgress.selected_track_artifact_path,
      "",
    ),
  };
}

export function buildRuntimeSummary({ autonomy, observability } = {}) {
  const autonomyPayload = asRecord(autonomy);
  const memory = asRecord(autonomyPayload.memory_pressure);
  const board = asRecord(autonomyPayload.board);
  const highImpact = asRecord(autonomyPayload.high_impact_policy_state);
  const latestResult = asRecord(
    autonomyPayload.latest_operation_result ||
      autonomyPayload.latest_result,
  );
  const latestOperation = asRecord(
    autonomyPayload.latest_operation ||
      autonomyPayload.latest_proposed_operation ||
      autonomyPayload.proposed_operation,
  );
  const boardState = text(
    board.status,
    board.decision,
    latestResult.decision_id ? "approved decision recorded" : "",
    autonomyPayload.latest_board_state,
    "unknown",
  );
  return {
    runtimeState: text(autonomyPayload.runtime_state, "unknown"),
    loopIteration: numberValue(autonomyPayload.loop_iteration),
    boardState,
    latestAction: text(latestOperation.action, latestResult.action, "not recorded"),
    latestResult: text(latestResult.status, asRecord(latestResult.result).status, "unknown"),
    latestDurationMs: numberValue(latestResult.duration_ms),
    highImpactState: text(
      highImpact.status,
      highImpact.state,
      highImpact.policy_state,
      highImpact.mode,
      typeof autonomyPayload.high_impact_policy_state === "string"
        ? autonomyPayload.high_impact_policy_state
        : "",
      "default gated",
    ),
    churnState: text(autonomyPayload.churn_state, "unknown"),
    churnBreaker: Boolean(autonomyPayload.churn_breaker_active),
    trustedTriageState: text(
      asRecord(autonomyPayload.trusted_source_triage).status,
      autonomyPayload.latest_trusted_source_status,
      "unknown",
    ),
    memoryPercent: numberValue(memory.memory_percent),
    memoryPressure: text(memory.pressure_band, "unknown"),
    memorySmoothing: text(memory.memory_smoothing_state, "normal"),
    memorySpillProfile: text(memory.memory_spill_profile, "balanced"),
    spillMode: text(memory.spill_mode, "move_cold"),
    latestSpillAction: text(memory.latest_spill_action, "none"),
    diskSpillBytes: numberValue(memory.disk_spill_bytes),
    runtimeLogSpillBytes: numberValue(memory.runtime_log_spill_bytes),
    runtimeLogBundleBytes: numberValue(memory.runtime_log_bundle_bytes),
    runtimeLogBundleCount: numberValue(memory.runtime_log_bundle_count),
    runtimeLogSmallFileBacklogCount: numberValue(memory.runtime_log_small_file_backlog_count),
    runtimeLogBundleLatestResult: text(memory.runtime_log_bundle_latest_result, "not checked"),
    coldArtifactSpillBytes: numberValue(memory.cold_artifact_spill_bytes),
    spillVolumeBytes: numberValue(memory.spill_volume_bytes),
    spillPointerCount: numberValue(memory.spill_pointer_count),
    spillBacklogCount: numberValue(memory.spill_backlog_count),
    latestSpillResult: text(memory.latest_spill_result, "unknown"),
    spillSweeperState: text(memory.spill_sweeper_state, "idle"),
    spillActivityState: text(memory.spill_activity_state, "idle"),
    nextSpillDueAt: text(memory.next_spill_due_at, "not scheduled"),
    runtimeLogSegmentCount: numberValue(memory.runtime_log_segment_count),
    runtimeLogActiveTailBytes: numberValue(memory.runtime_log_active_tail_bytes),
    coldArtifactBacklogBytes: numberValue(memory.cold_artifact_backlog_bytes),
    spillBudgetBytes: numberValue(memory.spill_budget_bytes),
    spillBudgetUsedBytes: numberValue(memory.spill_budget_used_bytes),
    ledgerIndexState: text(autonomyPayload.ledger_index_state, memory.ledger_index_state, "not reported"),
    dataAtRestCatalogState: text(
      autonomyPayload.data_at_rest_catalog_state,
      memory.data_at_rest_catalog_state,
      "not reported",
    ),
    librarianState: text(autonomyPayload.librarian_state, "unknown"),
    librarianPackCount: numberValue(autonomyPayload.librarian_pack_count),
    librarianReusableCount: numberValue(autonomyPayload.librarian_reusable_count),
    oomGuard: text(memory.oom_guard_state, "normal"),
    otelStatus: text(asRecord(observability).status, asRecord(observability).otel_status, "unknown"),
    refreshState: text(asRecord(observability).refresh_state, "unknown"),
  };
}
