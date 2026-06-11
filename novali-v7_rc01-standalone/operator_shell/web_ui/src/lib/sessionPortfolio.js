import {
  classifyAttentionArchiveState,
  loadAttentionMemory,
  summarizeCurrentSessionMemory,
} from "./attentionMemory.js";

const SESSION_PORTFOLIO_LIMIT = 6;

export const SESSION_PORTFOLIO_BUCKET_ORDER = [
  "new_blocking_now",
  "stale_escalated_blocking",
  "seen_unresolved_blocking",
  "acknowledged_unresolved_blocking",
  "resumable",
  "running_waiting",
  "completed_halted",
  "informational_recent_history",
  "resolved_history",
  "clear",
];

function asText(value, fallback = "") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function asNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseDateMs(value) {
  const raw = asText(value);
  if (!raw) {
    return 0;
  }
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : 0;
}

function isBlockingArchiveState(stateKey) {
  return (
    stateKey === "new_blocking" ||
    stateKey === "seen_unresolved_blocking" ||
    stateKey === "acknowledged_unresolved_blocking" ||
    stateKey === "stale_escalated_blocking"
  );
}

function isCompletedOrHaltedEntry(entry) {
  const lifecycle = asText(entry?.lifecycle_state).toLowerCase();
  const stopReason = asText(entry?.stop_reason).toLowerCase();
  const nextActionLabel = asText(entry?.next_action_label).toLowerCase();
  const policyHeadroomSummary = asText(entry?.policy_headroom_summary).toLowerCase();
  const currentCycle = asNumber(entry?.current_cycle, 0);
  const maxCycles = asNumber(entry?.max_cycles, 0);
  const boundedCyclesExhausted = maxCycles > 0 && currentCycle >= maxCycles;
  const zeroCycleHeadroom =
    policyHeadroomSummary.includes("0 total cycle(s) remain") ||
    policyHeadroomSummary.includes("0 total cycles remain");
  return (
    lifecycle.includes("completed") ||
    lifecycle.includes("halt") ||
    lifecycle.includes("failed") ||
    stopReason.includes("completed") ||
    stopReason.includes("halt") ||
    stopReason.includes("operator_stop") ||
    stopReason.includes("error") ||
    (boundedCyclesExhausted && (zeroCycleHeadroom || nextActionLabel.includes("review results")))
  );
}

function hasBlockingArchiveState(archiveState) {
  return (
    archiveState === "new_blocking" ||
    archiveState === "stale_escalated_blocking" ||
    archiveState === "seen_unresolved_blocking" ||
    archiveState === "acknowledged_unresolved_blocking"
  );
}

function isActiveReviewInterventionEntry(entry, archiveState) {
  if (!hasBlockingArchiveState(archiveState)) {
    return false;
  }
  const lifecycle = asText(entry?.lifecycle_state).toLowerCase();
  const stopReason = asText(entry?.stop_reason).toLowerCase();
  const nextActionLabel = asText(entry?.next_action_label).toLowerCase();
  const nextActionDetail = asText(entry?.next_action_detail).toLowerCase();
  return (
    lifecycle.includes("intervention") ||
    lifecycle.includes("review") ||
    stopReason.includes("intervention") ||
    stopReason.includes("review") ||
    nextActionLabel.includes("approve bounded continuation") ||
    nextActionLabel.includes("resolve") ||
    nextActionDetail.includes("approve, defer, or reject") ||
    nextActionDetail.includes("review the bounded")
  );
}

function isResumableEntry(entry, archiveState) {
  return !isBlockingArchiveState(archiveState) && Boolean(entry?.resume_ready_after_next_action);
}

function isRunningWaitingEntry(entry) {
  const lifecycle = asText(entry?.lifecycle_state).toLowerCase();
  return (
    lifecycle === "running" ||
    lifecycle === "resuming" ||
    lifecycle === "seeded" ||
    lifecycle === "waiting_for_next_invocation" ||
    lifecycle === "paused_for_budget"
  );
}

function queueBucketRank(bucket) {
  const index = SESSION_PORTFOLIO_BUCKET_ORDER.indexOf(bucket);
  return index >= 0 ? index : SESSION_PORTFOLIO_BUCKET_ORDER.length;
}

export function portfolioBucketLabel(bucket) {
  if (bucket === "new_blocking_now") return "New blocking now";
  if (bucket === "stale_escalated_blocking") return "Stale escalated blocking";
  if (bucket === "seen_unresolved_blocking") return "Seen unresolved blocking";
  if (bucket === "acknowledged_unresolved_blocking") return "Acknowledged unresolved blocking";
  if (bucket === "resumable") return "Resumable";
  if (bucket === "running_waiting") return "Running / waiting";
  if (bucket === "completed_halted") return "Completed / halted";
  if (bucket === "informational_recent_history") return "Informational recent history";
  if (bucket === "resolved_history") return "Resolved history";
  return "Clear";
}

export function portfolioAttentionStateLabel(stateKey) {
  if (stateKey === "new_blocking") return "New blocking";
  if (stateKey === "stale_escalated_blocking") return "Stale escalated";
  if (stateKey === "seen_unresolved_blocking") return "Seen unresolved";
  if (stateKey === "acknowledged_unresolved_blocking") return "Acknowledged unresolved";
  if (stateKey === "resolved_history") return "Resolved history";
  if (stateKey === "informational_history") return "Informational history";
  return "Clear";
}

export function portfolioAttentionStateTone(stateKey) {
  if (stateKey === "new_blocking") return "warning";
  if (stateKey === "stale_escalated_blocking") return "danger";
  if (stateKey === "seen_unresolved_blocking") return "info";
  if (stateKey === "acknowledged_unresolved_blocking") return "success";
  if (stateKey === "informational_history") return "phase";
  if (stateKey === "resolved_history") return "success";
  return "info";
}

export function classifyPortfolioSessionBucket(entry, options = {}) {
  const archiveState = classifyAttentionArchiveState(entry, options);
  if (isActiveReviewInterventionEntry(entry, archiveState)) {
    if (archiveState === "new_blocking") return "new_blocking_now";
    if (archiveState === "stale_escalated_blocking") return "stale_escalated_blocking";
    if (archiveState === "seen_unresolved_blocking") return "seen_unresolved_blocking";
    if (archiveState === "acknowledged_unresolved_blocking") return "acknowledged_unresolved_blocking";
  }
  if (isCompletedOrHaltedEntry(entry)) return "completed_halted";
  if (archiveState === "new_blocking") return "new_blocking_now";
  if (archiveState === "stale_escalated_blocking") return "stale_escalated_blocking";
  if (archiveState === "seen_unresolved_blocking") return "seen_unresolved_blocking";
  if (archiveState === "acknowledged_unresolved_blocking") return "acknowledged_unresolved_blocking";
  if (isResumableEntry(entry, archiveState)) return "resumable";
  if (archiveState === "informational_history") return "informational_recent_history";
  if (isRunningWaitingEntry(entry)) return "running_waiting";
  if (archiveState === "resolved_history") return "resolved_history";
  return "clear";
}

function recommendationLabel(bucket, shortlistSize) {
  if (bucket === "new_blocking_now") {
    return shortlistSize > 1
      ? "Open one of the sessions requiring immediate review"
      : "Open session requiring immediate review";
  }
  if (bucket === "stale_escalated_blocking") {
    return shortlistSize > 1
      ? "Open one of the stale unresolved blockers"
      : "Open stale unresolved blocker";
  }
  if (bucket === "seen_unresolved_blocking" || bucket === "acknowledged_unresolved_blocking") {
    return "Open unresolved blocker";
  }
  if (bucket === "resumable") return "Open resumable session";
  if (bucket === "running_waiting") return "Open running session summary";
  if (bucket === "completed_halted") return "Open completed session summary";
  if (bucket === "informational_recent_history") return "Open recent session update";
  return "Open recent session summary";
}

export function buildPortfolioNavigationTarget(card, options = {}) {
  const workspacePath = asText(options.workspacePath, "/shell/workspace");
  const shellPath = asText(options.shellPath, "/shell");
  const sessionId = asText(card?.session_id);
  const entryKey = asText(card?.entry_key);

  if (card?.current_session) {
    let focus = "campaign_handoff";
    let label = "Open current session summary";
    if (
      card?.queue_bucket === "new_blocking_now" ||
      card?.queue_bucket === "stale_escalated_blocking" ||
      card?.queue_bucket === "seen_unresolved_blocking" ||
      card?.queue_bucket === "acknowledged_unresolved_blocking"
    ) {
      focus = "current_blocker";
      label = "Open current blocker";
    } else if (card?.queue_bucket === "resumable") {
      focus = "continuation_controls";
      label = "Open continuation controls";
    }
    const params = new URLSearchParams();
    if (sessionId) params.set("portfolio_session", sessionId);
    if (entryKey) params.set("portfolio_entry_key", entryKey);
    params.set("portfolio_focus", focus);
    return {
      route: workspacePath,
      focus,
      label,
      session_id: sessionId,
      entry_key: entryKey,
      url: `${workspacePath}?${params.toString()}`,
    };
  }

  const params = new URLSearchParams();
  if (sessionId) params.set("portfolio_session", sessionId);
  if (entryKey) params.set("portfolio_entry_key", entryKey);
  params.set("portfolio_focus", "portfolio_history");
  return {
    route: shellPath,
    focus: "portfolio_history",
    label: "View session summary",
    session_id: sessionId,
    entry_key: entryKey,
    url: `${shellPath}?${params.toString()}#session-portfolio`,
  };
}

export function buildPortfolioRecommendation(cards = [], options = {}) {
  if (!Array.isArray(cards) || cards.length === 0) {
    return null;
  }
  const topCard = cards[0];
  const shortlist = cards.filter((card) => card.queue_rank === topCard.queue_rank).slice(0, 3);
  return {
    label: recommendationLabel(topCard.queue_bucket, shortlist.length),
    detail:
      shortlist.length > 1
        ? `${shortlist.length} sessions share the same current queue priority. Open one of the listed sessions to act on the next truthful blocker.`
        : topCard.current_blocker || topCard.next_action_detail || "Open the next truthful session surface.",
    bucket: topCard.queue_bucket,
    bucket_label: topCard.queue_bucket_label,
    target_session_id: topCard.session_id,
    target_entry_key: topCard.entry_key,
    navigation: buildPortfolioNavigationTarget(topCard, options),
    shortlist,
  };
}

export function buildSessionPortfolio(memory, options = {}) {
  const currentMemory = loadAttentionMemory(memory);
  const currentSessionId = asText(options.currentSessionId);
  const nowMs = asNumber(options.nowMs, Date.now());
  const cards = Object.entries(currentMemory.sessions || {})
    .map(([sessionId]) => {
      const summary = summarizeCurrentSessionMemory(currentMemory, sessionId);
      const entry = summary.currentEntry || summary.latestResolved || summary.history?.[0] || null;
      if (!entry) {
        return null;
      }
      const archiveState = classifyAttentionArchiveState(entry, { nowMs });
      const bucket = classifyPortfolioSessionBucket(entry, { nowMs });
      return {
        session_id: sessionId,
        session_handle: asText(entry.session_handle, sessionId.slice(-12) || sessionId),
        entry_key: asText(entry.entry_key),
        lifecycle_state: asText(entry.lifecycle_state),
        state_label: asText(entry.state_label || entry.lifecycle_state, "Unknown"),
        state_family: asText(entry.state_family),
        stop_reason: asText(entry.stop_reason),
        current_blocker: asText(entry.current_blocker, "No current blocker recorded."),
        next_action_label: asText(entry.next_action_label, "Open session"),
        next_action_detail: asText(entry.next_action_detail),
        current_cycle: asNumber(entry.current_cycle, 0),
        max_cycles: asNumber(entry.max_cycles, 0),
        checkpoint_count: asNumber(entry.checkpoint_count, 0),
        checkpoint_id: asText(entry.checkpoint_id),
        checkpoint_at: asText(entry.checkpoint_at),
        policy_headroom_summary: asText(entry.policy_headroom_summary),
        settings_summary: asText(entry.settings_summary),
        next_stop_boundary_label: asText(entry.next_stop_boundary_label),
        next_stop_boundary_summary: asText(entry.next_stop_boundary_summary),
        what_changed_summary: asText(entry.what_changed_summary),
        latest_progress_marker: asText(entry.latest_progress_marker),
        attention_blocking_count: asNumber(entry.attention_blocking_count, 0),
        attention_informational_count: asNumber(entry.attention_informational_count, 0),
        resume_ready_after_next_action: Boolean(entry.resume_ready_after_next_action),
        archive_state: archiveState,
        attention_state_label: portfolioAttentionStateLabel(archiveState),
        attention_state_tone: portfolioAttentionStateTone(archiveState),
        queue_bucket: bucket,
        queue_bucket_label: portfolioBucketLabel(bucket),
        queue_rank: queueBucketRank(bucket),
        current_session: currentSessionId ? sessionId === currentSessionId : false,
        current_or_recent_label: currentSessionId && sessionId === currentSessionId ? "Current active session" : "Recent session",
        history_count: Array.isArray(summary.history) ? summary.history.length : 0,
        unresolved_history_count: asNumber(summary.unresolvedBlockingCount, 0),
        resolved_history_count: asNumber(summary.resolvedCount, 0),
        stale_history_count: asNumber(summary.staleBlockingCount, 0),
        updated_at: asText(entry.updated_at || entry.created_at),
        updated_at_ms: parseDateMs(entry.updated_at || entry.created_at),
      };
    })
    .filter(Boolean)
    .sort((left, right) => {
      if (left.queue_rank !== right.queue_rank) {
        return left.queue_rank - right.queue_rank;
      }
      if (left.current_session !== right.current_session) {
        return left.current_session ? -1 : 1;
      }
      return right.updated_at_ms - left.updated_at_ms;
    })
    .slice(0, SESSION_PORTFOLIO_LIMIT);

  const bucket_counts = SESSION_PORTFOLIO_BUCKET_ORDER.reduce((accumulator, bucket) => {
    accumulator[bucket] = cards.filter((card) => card.queue_bucket === bucket).length;
    return accumulator;
  }, {});

  return {
    cards,
    bucket_counts,
    recommendation: buildPortfolioRecommendation(cards, options),
    limit: SESSION_PORTFOLIO_LIMIT,
  };
}
