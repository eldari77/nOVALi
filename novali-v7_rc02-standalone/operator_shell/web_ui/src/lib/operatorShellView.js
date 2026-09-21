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
const formatKind = (value) =>
  text(value, "unknown")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export function normalizeFrameworkTimezone(value, fallback = "America/Chicago") {
  const candidate = text(value, fallback);
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: candidate }).format(new Date(0));
    return candidate;
  } catch {
    return fallback;
  }
}

export function buildFrameworkClock({ operatorSettings = {}, now = Date.now() } = {}) {
  const settings = asRecord(operatorSettings);
  const timezone = normalizeFrameworkTimezone(
    settings.framework_timezone,
    text(asRecord(settings.framework_time).timezone, "America/Chicago"),
  );
  const date = new Date(now);
  const dateLabel = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
  const timeLabel = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    hourCycle: "h23",
  }).format(date);
  const timezoneParts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    timeZoneName: "short",
  }).formatToParts(date);
  return {
    timezone,
    dateLabel,
    timeLabel,
    timezoneLabel: text(
      timezoneParts.find((part) => part.type === "timeZoneName")?.value,
      timezone,
    ),
  };
}

export function formatFrameworkTimestamp(value, { operatorSettings = {} } = {}) {
  const source = text(value);
  if (!source || source === "an earlier refresh") return source;
  const timestamp = Date.parse(source);
  if (!Number.isFinite(timestamp)) return source;
  const settings = asRecord(operatorSettings);
  const timezone = normalizeFrameworkTimezone(
    settings.framework_timezone,
    text(asRecord(settings.framework_time).timezone, "America/Chicago"),
  );
  const date = new Date(timestamp);
  const dateLabel = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
  const timeLabel = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    hourCycle: "h23",
  }).format(date);
  const timezoneParts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    timeZoneName: "short",
  }).formatToParts(date);
  const timezoneLabel = text(
    timezoneParts.find((part) => part.type === "timeZoneName")?.value,
    timezone,
  );
  return `${dateLabel}, ${timeLabel} ${timezoneLabel}`;
}

export function formatFrameworkTimestampsInText(value, { operatorSettings = {} } = {}) {
  const source = text(value);
  if (!source) return "";
  return source.replace(
    /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})/g,
    (match) => formatFrameworkTimestamp(match, { operatorSettings }),
  );
}

export function buildCommandOverview({
  longRun,
  processLifecycle,
  autonomy,
  observability,
  operatorState,
  currentDirective,
  operatorSettings,
  now,
} = {}) {
  const longRunPayload = asRecord(asRecord(longRun).long_run || longRun);
  const guidance = asRecord(asRecord(longRun).operator_guidance);
  const autonomyPayload = asRecord(autonomy);
  const directivePayload = asRecord(currentDirective);
  const memory = asRecord(autonomyPayload.memory_pressure);
  const operatorPayload = asRecord(operatorState);
  const operator = asRecord(operatorPayload.operator_state || operatorPayload);
  const governedReadiness = asRecord(asRecord(operatorPayload.launch_readiness).governed);
  const lifecycle = asRecord(processLifecycle);
  const lifecycleWarnings = asArray(lifecycle.blocking_reasons).map((item) => text(item)).filter(Boolean);
  const processBlocked = lifecycle.can_start === false || lifecycleWarnings.length > 0;
  const primaryCta = asRecord(guidance.primary_cta);
  const directiveKnownUnselected = directivePayload.directive_selected === false;
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
  const firstLaunchReady = Boolean(governedReadiness.can_launch || operator.governed_ready);
  const oomState = text(memory.oom_guard_state, longRunPayload.oom_guard_state, "normal");
  const memoryState = text(
    memory.memory_smoothing_state,
    longRunPayload.memory_smoothing_state,
    "normal",
  );
  let safetyTone = "healthy";
  if (emergencyStop || oomState === "recycle_required" || oomState === "hibernate_required") {
    safetyTone = "danger";
  } else if (
    staleRecovery ||
    reviewRequired ||
    processBlocked ||
    memoryState === "cooling" ||
    memoryState === "spilling"
  ) {
    safetyTone = "attention";
  }
  const headline = emergencyStop
    ? "Emergency stop active"
    : staleRecovery
      ? "Recovery attention needed"
      : reviewRequired
        ? "Operator review needed"
        : processBlocked
          ? "Process lifecycle attention"
          : readyToContinue
          ? "Ready to continue"
          : text(guidance.state_family, longRunPayload.lifecycle_state, "Monitoring");
  const primaryAction = {
    id: text(primaryCta.action_id, readyToContinue ? "continue" : firstLaunchReady ? "start_governed" : "review"),
    label: text(
      primaryCta.label,
      readyToContinue
        ? "Continue current bounded session"
        : firstLaunchReady
          ? "Start governed execution"
          : "Review state",
    ),
    enabled: !emergencyStop && !staleRecovery && !processBlocked,
  };
  if (/start governed execution/i.test(primaryAction.label) && directiveKnownUnselected) {
    primaryAction.id = "launch_prerequisites";
    primaryAction.label = "Resolve launch prerequisites";
    primaryAction.enabled = false;
  }
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
      directiveKnownUnselected && /start governed execution|resolve launch prerequisites/i.test(primaryAction.label)
        ? "Select or approve a directive before governed execution can seed a bounded checkpoint."
        : "",
      lifecycleWarnings[0],
      longRunPayload.recommended_next_action,
      guidance.recommended_next_action,
      "Inspect the next safe operator action.",
    ),
    lifecycleWarnings,
    processLifecycleBlocked: processBlocked,
    primaryAction,
    frameworkClock: buildFrameworkClock({ operatorSettings, now }),
  };
}

export function resolvePrimarySafeAction(primaryAction = {}) {
  const actionId = text(primaryAction.id, "review");
  const label = text(primaryAction.label);
  if (actionId === "start_governed" || /start governed execution/i.test(label)) {
    return { actionId: "start_governed", request: "start_governed" };
  }
  if (actionId === "continue") {
    return { actionId, request: "continue_long_run" };
  }
  return { actionId, request: "review_state" };
}

export function askDrawerAccessibilityProps(open) {
  return open ? { "aria-hidden": undefined, inert: undefined } : { "aria-hidden": true, inert: "" };
}

export function buildOperatorTruthSummary({
  overview = {},
  conveyorSummary = {},
  returnsWorkbench = {},
  refreshMeta = {},
  operatorSettings = {},
  loading = false,
} = {}) {
  const summary = asRecord(conveyorSummary);
  const meta = asRecord(refreshMeta);
  const summaryCountsCurrent = summary.counts_current !== false && !summary.summary_unavailable;
  const pendingReturns = numberValue(
    summaryCountsCurrent ? asRecord(returnsWorkbench).badgeCount : 0,
    summaryCountsCurrent
      ? numberValue(summary.pending_return_count) + numberValue(summary.pending_support_request_count)
      : 0,
  );
  const activeChildren = summaryCountsCurrent ? numberValue(summary.active_child_count) : 0;
  const queuedDirectives = summaryCountsCurrent
    ? numberValue(summary.queued_directive_count, numberValue(asRecord(summary.directive_counts_by_state).queued))
    : 0;
  const summaryStale = Boolean(meta.conveyorSummaryStale);
  const deepStale = Boolean(
    meta.conveyorStatusStale ||
      meta.conveyorSupportRequestsStale ||
      meta.conveyorOvernightReadinessStale,
  );
  const freshness = loading
    ? "refreshing"
    : summaryStale
      ? "stale"
      : deepStale
        ? "partial"
        : "live";
  const staleWarning = formatFrameworkTimestampsInText(
    text(meta.conveyorSummaryWarning, meta.conveyorRefreshWarning),
    { operatorSettings },
  );
  if (summaryStale && Object.keys(summary).length) {
    return {
      label: "Operator Truth",
      headline: "Conveyor truth is stale",
      detail: text(staleWarning, "Conveyor summary refresh failed; showing cached data."),
      freshness,
      safetyTone: "attention",
      primaryAction: { id: "open_conveyor", label: "Open conveyor", enabled: true, targetTab: "conveyor" },
      metrics: { pendingReturns, activeChildren, queuedDirectives },
    };
  }
  if (pendingReturns > 0) {
    return {
      label: "Operator Truth",
      headline: pendingReturns === 1 ? "1 return needs review" : `${pendingReturns} returns need review`,
      detail: "Returned directive work or kernel support is waiting for operator decision.",
      freshness,
      safetyTone: "attention",
      primaryAction: { id: "open_returns", label: "Review returns", enabled: true, targetTab: "returns" },
      metrics: { pendingReturns, activeChildren, queuedDirectives },
    };
  }
  if (activeChildren > 0) {
    return {
      label: "Operator Truth",
      headline: activeChildren === 1 ? "1 child agent active" : `${activeChildren} child agents active`,
      detail: `Conveyor autonomy is running with ${queuedDirectives} queued directive${queuedDirectives === 1 ? "" : "s"}.`,
      freshness,
      safetyTone: "healthy",
      primaryAction: { id: "open_conveyor", label: "Open conveyor", enabled: true, targetTab: "conveyor" },
      metrics: { pendingReturns, activeChildren, queuedDirectives },
    };
  }
  if (text(asRecord(overview).runtimeState) === "running" && /not_started|unknown/i.test(text(asRecord(overview).headline))) {
    return {
      label: "Operator Truth",
      headline: "Core growth running",
      detail: "Autonomy is active even though governed long-run execution has not seeded a checkpoint.",
      freshness,
      safetyTone: text(overview.safetyTone, "healthy"),
      primaryAction: { id: "open_growth", label: "Open framework growth", enabled: true, targetTab: "growth" },
      metrics: { pendingReturns, activeChildren, queuedDirectives },
    };
  }
  return {
    label: "Operator Truth",
    headline: text(overview.headline, loading ? "Refreshing operator truth" : "Monitoring"),
    detail: text(overview.nextAction, "Inspect the next safe operator action."),
    freshness,
    safetyTone: text(overview.safetyTone, "healthy"),
    primaryAction: {
      ...asRecord(overview.primaryAction),
      enabled: asRecord(overview.primaryAction).enabled !== false,
      targetTab: "queue",
    },
    metrics: { pendingReturns, activeChildren, queuedDirectives },
  };
}

export const OPERATOR_TOOLBAR_TABS = [
  { id: "overview", label: "Overview" },
  { id: "queue", label: "Attention Queue" },
  { id: "conveyor", label: "Conveyor" },
  { id: "returns", label: "Returns" },
  { id: "growth", label: "Framework Growth" },
  { id: "runtime", label: "Autonomy + Runtime" },
  { id: "librarian", label: "Librarian" },
  { id: "settings", label: "Settings" },
];

export function buildOperatorToolbarItems({ activeTab = "overview", returnsBadgeCount = 0, collapsed = false } = {}) {
  return OPERATOR_TOOLBAR_TABS.map((item) => {
    const badge = item.id === "returns" ? numberValue(returnsBadgeCount) : 0;
    const ariaLabel = badge > 0 ? `${item.label}, ${badge} pending` : item.label;
    return {
      ...item,
      active: item.id === activeTab,
      badge,
      ariaLabel,
      displayLabel: collapsed ? "" : item.label,
    };
  });
}

export function buildOperatorTopVitals({ overview = {}, operatorTruth = {} } = {}) {
  const truth = asRecord(operatorTruth);
  const metrics = asRecord(truth.metrics);
  return [
    { label: "Freshness", value: text(truth.freshness, "unknown"), tone: text(truth.freshness, "unknown") },
    { label: "Active children", value: String(numberValue(metrics.activeChildren)) },
    { label: "Returns", value: String(numberValue(metrics.pendingReturns)) },
    { label: "Queued", value: String(numberValue(metrics.queuedDirectives)) },
    { label: "Autonomy", value: text(asRecord(overview).runtimeState, "unknown") },
    {
      label: "Telemetry",
      value: text(asRecord(overview).observabilityState, "unknown"),
    },
  ];
}

export function buildOperatorActivitySnapshot({
  overview = {},
  operatorTruth = {},
  conveyorSummary = {},
  conveyorWorkbenchSummary = {},
  refreshMeta = {},
  operatorSettings = {},
} = {}) {
  const truth = asRecord(operatorTruth);
  const meta = asRecord(refreshMeta);
  const summary = asRecord(conveyorSummary);
  const deepSummary = asRecord(conveyorWorkbenchSummary);
  const hasCurrentSummary =
    Object.keys(summary).length > 0 &&
    !Boolean(meta.conveyorSummaryStale) &&
    summary.counts_current !== false &&
    !summary.summary_unavailable;
  const deepStale = Boolean(
    meta.conveyorStatusStale ||
      meta.conveyorSupportRequestsStale ||
      meta.conveyorOvernightReadinessStale,
  );
  const currentChildren = numberValue(summary.active_child_count);
  const currentReturns = numberValue(
    summary.pending_return_count,
    numberValue(asRecord(truth.metrics).pendingReturns),
  );
  const currentQueued = numberValue(
    summary.queued_directive_count,
    numberValue(asRecord(summary.directive_counts_by_state).queued),
  );
  const staleChildCount = numberValue(deepSummary.activeChildren);
  const formattedLastDeepRefresh = formatFrameworkTimestamp(meta.conveyorLastRefreshedAt, { operatorSettings });
  const staleDetail = deepStale
    ? `Deep conveyor data is cached${formattedLastDeepRefresh ? ` from ${formattedLastDeepRefresh}` : ""}.`
    : "";
  return {
    lane: {
      label: "Live lane",
      value: text(truth.headline, "Monitoring"),
      detail: text(truth.freshness, "unknown"),
    },
    children: {
      label: hasCurrentSummary ? "Current children" : "Current children",
      value: hasCurrentSummary ? String(currentChildren) : "unknown",
      detail: !hasCurrentSummary && staleChildCount > 0 ? `Last deep check: ${staleChildCount}` : "",
    },
    returns: {
      label: hasCurrentSummary ? "Current returns" : "Current returns",
      value: hasCurrentSummary ? String(currentReturns) : "unknown",
    },
    queued: {
      label: hasCurrentSummary ? "Current queued" : "Current queued",
      value: hasCurrentSummary ? String(currentQueued) : "unknown",
    },
    telemetry: {
      label: "Telemetry",
      value: text(asRecord(overview).observabilityState, "unknown"),
    },
    countsAreCurrent: hasCurrentSummary,
    staleDetail,
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

const supportRequestQueueItem = (request) => ({
  review_item_id: text(request.support_request_id, request.return_packet_id, request.directive_id, "conveyor-support-request"),
  title: formatKind(request.capability || "Kernel support request"),
  reason_summary: text(
    request.reason,
    request.directive_id ? `Support request for ${request.directive_id}.` : "",
    "Child requested kernel-mediated trusted-source support.",
  ),
  action_label: "Approve support request",
  severity: "operator_review_required",
  bucket: "blocker",
  queue_item_kind: "conveyor_support_request",
  support_request: request,
});

const dispatchHardReviewQueueItem = (item) => ({
  ...item,
  review_item_id: text(item.review_item_id, item.action_type, "dispatch-hard-review"),
  title: text(item.title, "Dispatch hard-review blocker"),
  reason_summary: text(
    item.reason_summary,
    item.reason,
    item.action_needed,
    "Dispatch is blocked by an operator review item.",
  ),
  action_label: text(
    item.available_disposition_action_label,
    item.recommended_action,
    item.action_needed,
    "Review blocker",
  ),
  severity: text(item.severity, "critical"),
  blocks_continuation: true,
  bucket: "blocker",
  queue_item_kind: "external_adapter_review",
});

const seedableDispatchQueueItem = (dispatch) => {
  const queued = Number(dispatch.queued_directive_count || 0);
  const active = Number(dispatch.active_child_count || 0);
  const firstBlocker = text(asArray(dispatch.blocking_reasons)[0], "");
  const schedulerTickReady =
    text(dispatch.state) === "waiting_for_children" &&
    text(dispatch.recommended_action_id) === "conveyor_scheduler_tick";
  const actionLabel = schedulerTickReady
    ? "Run conveyor scheduler"
    : "Run bootstrap, then start governed execution";
  return {
    review_item_id: "seedable-conveyor-dispatch",
    title: "Child dispatch is ready to start",
    reason_summary: [
      `Queued directives: ${queued}.`,
      `Active children: ${active}.`,
      firstBlocker ? `Next prerequisite: ${firstBlocker}.` : "",
    ]
      .filter(Boolean)
      .join(" "),
    action_label: actionLabel,
    severity: "operator_action_required",
    blocks_continuation: true,
    bucket: "blocker",
    queue_item_kind: "seedable_conveyor_dispatch",
    action_id: "start_seedable_conveyor_dispatch",
    recommended_action: actionLabel,
  };
};

const canStartConveyorDispatch = (dispatch) => {
  if (text(dispatch.state) === "seedable_from_conveyor_queue") {
    return (
      Number(dispatch.active_child_count || 0) <= 0 &&
      Boolean(dispatch.eligible_for_safe_auto_continue) &&
      text(dispatch.recommended_action_id) === "governed_start_next_invocation"
    );
  }
  return (
    text(dispatch.state) === "waiting_for_children" &&
    text(dispatch.recommended_action_id) === "conveyor_scheduler_tick" &&
    Number(dispatch.queued_directive_count || 0) > 0 &&
    Number(dispatch.active_child_count || 0) <= 0
  );
};

export function buildAttentionQueue({ operatorState, conveyorSupportRequests, dispatchHealth } = {}) {
  const operator = asRecord(operatorState);
  const intervention = asRecord(operator.intervention);
  const portfolio = asRecord(operator.session_portfolio || operator.portfolio);
  const supportPayload = asRecord(conveyorSupportRequests);
  const dispatch = asRecord(dispatchHealth);
  const supportRequests = asArray(supportPayload.support_requests)
    .map((item) => asRecord(item))
    .filter((item) => text(item.support_state) === "pending_operator_review" || item.operator_review_required === true)
    .map((item) => supportRequestQueueItem(item));
  const dispatchBlockers = asArray(dispatch.hard_review_blockers)
    .map((item) => asRecord(item))
    .filter((item) => Boolean(item.blocks_continuation) || text(item.reason_class) === "external_adapter_review")
    .map((item) => dispatchHardReviewQueueItem(item));
  const seedableDispatch =
    dispatchBlockers.length === 0 &&
    canStartConveyorDispatch(dispatch)
      ? [seedableDispatchQueueItem(dispatch)]
      : [];
  const reviewItems = asArray(intervention.queue_items).map((item) => asRecord(item));
  const seenReviewIds = new Set(
    dispatchBlockers.map((item) => text(item.review_item_id)).filter(Boolean),
  );
  const portfolioCards = asArray(portfolio.cards || portfolio.items || operator.session_portfolio_cards).map((item) =>
    asRecord(item),
  );
  const blockers = [
    ...supportRequests,
    ...dispatchBlockers,
    ...seedableDispatch,
    ...reviewItems.filter(
      (item) =>
        Boolean(item.blocks_continuation || item.severity === "critical") &&
        !seenReviewIds.has(text(item.review_item_id)),
    ),
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
  const latestDirectiveEvidence = asRecord(autonomyPayload.latest_directive_evidence);
  const latest = asRecord(
    (Object.keys(latestDirectiveEvidence).length > 0 &&
      Boolean(
        latestDirectiveEvidence.directive_dossier_materially_new ||
          latestDirectiveEvidence.directive_dossier_artifact_relative_path ||
          latestDirectiveEvidence.latest_directive_dossier_ref ||
          latestDirectiveEvidence.deliverable_artifact_materially_new ||
          latestDirectiveEvidence.deliverable_artifact_relative_path,
      ) &&
      latestDirectiveEvidence) ||
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
  const deliverableArtifactMaterialDelta = Boolean(
    latest.deliverable_artifact_materially_new ||
      meaningful.deliverable_artifact_materially_new ||
      directiveTrackProgress.deliverable_artifact_materially_new,
  );
  const deliverableArtifactCredited = Boolean(meaningful.deliverable_artifact_delta_credited);
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
      deliverableArtifactCredited ||
      deliverableArtifactMaterialDelta ||
      dossierCredited ||
      dossierMaterialDelta ||
      trackCredited ||
      trackMaterialDelta,
  );
  const meaningfulCreditKind =
    meaningfulDelta && (deliverableArtifactCredited || deliverableArtifactMaterialDelta)
      ? "deliverable_artifact"
      : meaningfulDelta && (dossierCredited || dossierMaterialDelta)
      ? "directive_dossier"
      : meaningfulDelta && (trackCredited || trackMaterialDelta)
        ? "directive_track"
        : "none";
  const meaningfulCreditLabel =
    meaningfulCreditKind === "deliverable_artifact"
      ? "Concrete artifact credited"
      : meaningfulCreditKind === "directive_dossier"
      ? "Dossier delta credited"
      : meaningfulCreditKind === "directive_track"
        ? "Track delta credited"
        : "No credited delta";
  const meaningfulRejectionReason =
    meaningfulCreditKind === "deliverable_artifact"
      ? text(
          latest.deliverable_artifact_rejection_reason,
          meaningful.deliverable_artifact_rejection_reason,
          directiveTrackProgress.deliverable_artifact_rejection_reason,
          "none",
        )
      : meaningfulCreditKind === "directive_dossier"
        ? dossierRejectionReason
        : trackRejectionReason;
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
    deliverableArtifactCredited,
    deliverableArtifactMaterialDelta,
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
    directiveProgressCreditKind: text(
      latest.directive_progress_credit_kind,
      meaningful.directive_progress_credit_kind,
      meaningfulCreditKind,
      "none",
    ),
    packSummaryQuality: text(
      latest.pack_summary_quality,
      meaningful.pack_summary_quality,
      directiveTrackProgress.pack_summary_quality,
      "not_recorded",
    ),
    packDistillationState: text(
      latest.pack_distillation_state,
      meaningful.pack_distillation_state,
      directiveTrackProgress.pack_distillation_state,
      "not_recorded",
    ),
    packUsefulnessState: text(
      latest.pack_usefulness_state,
      meaningful.pack_usefulness_state,
      directiveTrackProgress.pack_usefulness_state,
      "not_recorded",
    ),
    packDistilledClaimCount: numberValue(
      latest.pack_distilled_claim_count,
      numberValue(
        meaningful.pack_distilled_claim_count,
        numberValue(directiveTrackProgress.pack_distilled_claim_count, 0),
      ),
    ),
    packDistilledValidationQuestionCount: numberValue(
      latest.pack_distilled_validation_question_count,
      numberValue(
        meaningful.pack_distilled_validation_question_count,
        numberValue(directiveTrackProgress.pack_distilled_validation_question_count, 0),
      ),
    ),
    deliverableContentQuality: text(
      latest.directive_deliverable_content_quality,
      meaningful.directive_deliverable_content_quality,
      directiveTrackProgress.directive_deliverable_content_quality,
      "not_recorded",
    ),
    nextConcreteArtifact: text(
      latest.next_concrete_artifact,
      meaningful.next_concrete_artifact,
      directiveTrackProgress.next_concrete_artifact,
      "",
    ),
    deliverableArtifactKind: text(
      latest.deliverable_artifact_kind,
      meaningful.deliverable_artifact_kind,
      directiveTrackProgress.deliverable_artifact_kind,
      "",
    ),
    deliverableArtifactPath: text(
      latest.deliverable_artifact_relative_path,
      meaningful.deliverable_artifact_relative_path,
      directiveTrackProgress.deliverable_artifact_relative_path,
      "",
    ),
    deliverableArtifactRef: text(
      latest.deliverable_artifact_ref,
      meaningful.deliverable_artifact_ref,
      directiveTrackProgress.deliverable_artifact_ref,
      "",
    ),
    deliverableArtifactSignature: text(
      latest.deliverable_artifact_signature,
      meaningful.deliverable_artifact_signature,
      directiveTrackProgress.deliverable_artifact_signature,
      "",
    ),
    deliverableMaturityState: text(
      latest.directive_deliverable_maturity_state,
      meaningful.directive_deliverable_maturity_state,
      directiveTrackProgress.directive_deliverable_maturity_state,
      "not_recorded",
    ),
    deliverableNextMaturityState: text(
      latest.directive_deliverable_next_maturity_state,
      meaningful.directive_deliverable_next_maturity_state,
      directiveTrackProgress.directive_deliverable_next_maturity_state,
      "not_recorded",
    ),
    deliverableMaturityTarget: text(
      latest.directive_deliverable_maturity_target,
      meaningful.directive_deliverable_maturity_target,
      directiveTrackProgress.directive_deliverable_maturity_target,
      "not_recorded",
    ),
    directiveTrackRotationReason: text(
      latest.directive_track_rotation_reason,
      meaningful.directive_track_rotation_reason,
      directiveTrackProgress.directive_track_rotation_reason,
      "not_recorded",
    ),
    artifactDensityState: text(
      latest.directive_artifact_density_state,
      meaningful.directive_artifact_density_state,
      directiveTrackProgress.directive_artifact_density_state,
      "not_recorded",
    ),
    artifactMissingDensityRequirements: asArray(
      latest.directive_artifact_missing_density_requirements ||
        meaningful.directive_artifact_missing_density_requirements ||
        directiveTrackProgress.directive_artifact_missing_density_requirements,
    ).map((item) => text(item)).filter(Boolean),
    capabilityQualityGateResults: asRecord(
      latest.capability_quality_gate_results ||
        meaningful.capability_quality_gate_results ||
        directiveTrackProgress.capability_quality_gate_results,
    ),
    continuationReadinessAction: text(
      latest.continuation_readiness_action,
      meaningful.continuation_readiness_action,
      directiveTrackProgress.continuation_readiness_action,
      "not_recorded",
    ),
    nextConcreteArtifactState: text(
      latest.next_concrete_artifact_state,
      meaningful.next_concrete_artifact_state,
      directiveTrackProgress.next_concrete_artifact_state,
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
  const growth = asRecord(autonomyPayload.autonomous_growth);
  const maturity = asRecord(autonomyPayload.nine_d_capability_maturity);
  const dominance = asRecord(
    maturity.continuation_dominance ||
      asRecord(autonomyPayload.latest_operation_proposal).continuation_dominance,
  );
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
    maturityBand: text(maturity.maturity_band, growth.nine_d_maturity_band, "seed"),
    criticalityScore: numberValue(maturity.criticality_score, growth.nine_d_criticality_score || 0),
    c1Complexity: numberValue(maturity.c1_complexity, growth.nine_d_c1_complexity || 0),
    c2SelfModel: numberValue(maturity.c2_self_model, growth.nine_d_c2_self_model || 0),
    c3ObserverStability: numberValue(
      maturity.c3_observer_stability,
      growth.nine_d_c3_observer_stability || 0,
    ),
    strictConsumptionGatePassed: Boolean(
      maturity.strict_consumption_gate_passed ||
        growth.nine_d_strict_consumption_gate_passed,
    ),
    strictConsumptionGateReason: text(
      maturity.consumption_gate_reason,
      asArray(maturity.threshold_blockers)[0],
      "missing_strict_consumption",
    ),
    continuationDominanceState: text(
      maturity.continuation_dominance_state,
      dominance.continuation_dominance_state,
      autonomyPayload.continuation_dominance_state,
      growth.continuation_dominance_state,
      "clear",
    ),
    governedContinuationsWithoutStrictUsefulness: numberValue(
      dominance.governed_continuations_without_strict_usefulness,
      numberValue(autonomyPayload.governed_continuations_without_strict_usefulness, 0),
    ),
    continuationDominanceThreshold: numberValue(dominance.threshold, 7),
    nextMaturityAction: text(
      maturity.next_maturity_action,
      dominance.recommended_action,
      asRecord(autonomyPayload.latest_operation_proposal).continuation_dominance_recommended_action,
      growth.nine_d_next_maturity_action,
      "adaptive_learning_synthesis",
    ),
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
