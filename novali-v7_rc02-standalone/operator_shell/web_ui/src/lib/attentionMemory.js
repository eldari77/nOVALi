const HISTORY_LIMIT = 8;
const DEFAULT_SNOOZE_MINUTES = 15;
const STALE_ESCALATION_MS = 15 * 1000;

function asText(value, fallback = "") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function asNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

export function createEmptyAttentionMemory() {
  return {
    schema_version: 1,
    sessions: {},
  };
}

export function loadAttentionMemory(raw) {
  if (!raw) {
    return createEmptyAttentionMemory();
  }
  try {
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!parsed || typeof parsed !== "object") {
      return createEmptyAttentionMemory();
    }
    return {
      schema_version: 1,
      sessions:
        parsed.sessions && typeof parsed.sessions === "object"
          ? clone(parsed.sessions)
          : {},
    };
  } catch {
    return createEmptyAttentionMemory();
  }
}

export function serializeAttentionMemory(memory) {
  return JSON.stringify(memory || createEmptyAttentionMemory());
}

function normalizeHistoryEntry(entry) {
  const localState = asText(entry?.local_state, "new");
  return {
    entry_key: asText(entry?.entry_key),
    session_id: asText(entry?.session_id),
    session_handle: asText(entry?.session_handle),
    checkpoint_id: asText(entry?.checkpoint_id),
    checkpoint_at: asText(entry?.checkpoint_at),
    lifecycle_state: asText(entry?.lifecycle_state),
    state_label: asText(entry?.state_label),
    stop_reason: asText(entry?.stop_reason),
    next_action_label: asText(entry?.next_action_label),
    next_action_detail: asText(entry?.next_action_detail),
    what_changed_summary: asText(entry?.what_changed_summary),
    current_blocker: asText(entry?.current_blocker),
    next_stop_boundary_label: asText(entry?.next_stop_boundary_label),
    next_stop_boundary_summary: asText(entry?.next_stop_boundary_summary),
    attention_blocking_count: asNumber(entry?.attention_blocking_count, 0),
    attention_informational_count: asNumber(entry?.attention_informational_count, 0),
    current_cycle: asNumber(entry?.current_cycle, 0),
    max_cycles: asNumber(entry?.max_cycles, 0),
    checkpoint_count: asNumber(entry?.checkpoint_count, 0),
    severity: asText(entry?.severity, "clear"),
    packet_id: asText(entry?.packet_id),
    state_family: asText(entry?.state_family),
    policy_headroom_summary: asText(entry?.policy_headroom_summary),
    settings_summary: asText(entry?.settings_summary),
    latest_progress_marker: asText(entry?.latest_progress_marker),
    notification_candidate: Boolean(entry?.notification_candidate),
    local_state:
      localState === "resolved" ||
      localState === "acknowledged" ||
      localState === "seen" ||
      localState === "snoozed"
        ? localState
        : "new",
    created_at: asText(entry?.created_at),
    updated_at: asText(entry?.updated_at),
    seen_at: asText(entry?.seen_at),
    acknowledged_at: asText(entry?.acknowledged_at),
    snoozed_until: asText(entry?.snoozed_until),
    resolved_at: asText(entry?.resolved_at),
    active: entry?.active !== false,
    continuation_resumed_after_packet: Boolean(entry?.continuation_resumed_after_packet),
    handoff_label: asText(entry?.handoff_label),
    resume_ready_after_next_action: Boolean(entry?.resume_ready_after_next_action),
    summary_signature: asText(entry?.summary_signature),
    last_notified_at: asText(entry?.last_notified_at),
  };
}

function isBlockingEntry(entry) {
  return asNumber(entry?.attention_blocking_count, 0) > 0 || asText(entry?.severity) === "blocking";
}

function isResolvedEntry(entry) {
  return !isBlockingEntry(entry) && entry?.local_state === "resolved";
}

function parseDateMs(value) {
  const raw = asText(value);
  if (!raw) {
    return 0;
  }
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : 0;
}

function staleEscalationAnchorMs(entry) {
  return (
    parseDateMs(entry?.acknowledged_at) ||
    parseDateMs(entry?.seen_at) ||
    parseDateMs(entry?.updated_at) ||
    parseDateMs(entry?.created_at)
  );
}

function isStaleEscalatedBlockingEntry(entry, options = {}) {
  const normalized = normalizeHistoryEntry(entry);
  if (!normalized.active || !isBlockingEntry(normalized) || normalized.local_state !== "acknowledged") {
    return false;
  }
  const anchorMs = staleEscalationAnchorMs(normalized);
  if (!anchorMs) {
    return false;
  }
  const nowMs = asNumber(options.nowMs, Date.now());
  return nowMs - anchorMs >= STALE_ESCALATION_MS;
}

function summarizeHandoffTransition(previousEntry, nextEntry) {
  if (!previousEntry) {
    return "new_attention";
  }
  if (asText(previousEntry?.entry_key) === asText(nextEntry?.entry_key)) {
    return "unchanged";
  }
  if (asText(previousEntry?.packet_id) !== asText(nextEntry?.packet_id)) {
    return "new_packet";
  }
  if (asText(previousEntry?.checkpoint_id) !== asText(nextEntry?.checkpoint_id)) {
    return "new_checkpoint";
  }
  if (asText(previousEntry?.current_blocker) !== asText(nextEntry?.current_blocker)) {
    return "changed_blocker";
  }
  if (asText(previousEntry?.severity) !== asText(nextEntry?.severity)) {
    return "changed_severity";
  }
  return "changed_summary";
}

function currentNotificationMode(notificationSupport) {
  const supported = Boolean(notificationSupport?.supported);
  const permission = asText(notificationSupport?.permission, "default");
  if (supported && permission === "granted") {
    return "browser";
  }
  return "in_app_only";
}

export function classifyAttentionArchiveState(entry, options = {}) {
  const normalized = normalizeHistoryEntry(entry);
  if (!normalized.entry_key) {
    return "clear";
  }
  if (normalized.active && isBlockingEntry(normalized)) {
    if (isStaleEscalatedBlockingEntry(normalized, options)) {
      return "stale_escalated_blocking";
    }
    if (normalized.local_state === "acknowledged") {
      return "acknowledged_unresolved_blocking";
    }
    if (normalized.local_state === "seen" || normalized.local_state === "snoozed") {
      return "seen_unresolved_blocking";
    }
    return "new_blocking";
  }
  if (normalized.attention_informational_count > 0) {
    return "informational_history";
  }
  if (normalized.local_state === "resolved" || !normalized.active) {
    return "resolved_history";
  }
  return "clear";
}

export function filterAttentionArchiveEntries(history, filterKey = "all", options = {}) {
  const normalizedHistory = Array.isArray(history) ? history.map(normalizeHistoryEntry) : [];
  const currentEntryKey = asText(options.currentEntryKey);
  const normalizedFilter = asText(filterKey, "all");
  return normalizedHistory.filter((entry) => {
    const stateKey = classifyAttentionArchiveState(entry, options);
    if (normalizedFilter === "current") {
      return !!currentEntryKey && entry.entry_key === currentEntryKey;
    }
    if (normalizedFilter === "unresolved") {
      return (
        stateKey === "new_blocking" ||
        stateKey === "seen_unresolved_blocking" ||
        stateKey === "acknowledged_unresolved_blocking" ||
        stateKey === "stale_escalated_blocking"
      );
    }
    if (normalizedFilter === "stale") {
      return stateKey === "stale_escalated_blocking";
    }
    if (normalizedFilter === "resolved") {
      return stateKey === "resolved_history";
    }
    if (normalizedFilter === "informational") {
      return stateKey === "informational_history";
    }
    return true;
  });
}

export function pickAttentionFocusTarget({
  currentPrimaryReviewItemId = "",
  attentionPacket = null,
  blockingItems = [],
} = {}) {
  const primaryReviewItemId = asText(currentPrimaryReviewItemId);
  if (primaryReviewItemId) {
    return {
      kind: "blocking_item",
      target_id: `attention-review-item-${primaryReviewItemId}`,
      reason: "current_primary_review_item",
    };
  }
  const normalizedBlockingItems = Array.isArray(blockingItems) ? blockingItems : [];
  const primaryBlockingItem =
    normalizedBlockingItems.find((item) => item?.blocks_continuation !== false) ||
    normalizedBlockingItems[0] ||
    null;
  const blockingReviewItemId = asText(
    primaryBlockingItem?.review_item_id || primaryBlockingItem?.review_id,
  );
  if (blockingReviewItemId) {
    return {
      kind: "blocking_item",
      target_id: `attention-review-item-${blockingReviewItemId}`,
      reason: "first_blocking_item",
    };
  }
  const packetId = asText(
    attentionPacket?.packet_id || attentionPacket?.review_packet_id || attentionPacket?.id,
  );
  if (packetId) {
    return {
      kind: "packet",
      target_id: `attention-packet-${packetId}`,
      reason: "attention_packet",
    };
  }
  if (attentionPacket && typeof attentionPacket === "object") {
    return {
      kind: "packet",
      target_id: "attention-packet-current",
      reason: "fallback_packet",
    };
  }
  if (normalizedBlockingItems.length) {
    return {
      kind: "picker",
      target_id: "attention-blocking-list",
      reason: "blocking_item_picker",
    };
  }
  return {
    kind: "none",
    target_id: "",
    reason: "no_blocking_target",
  };
}

export function buildHandoffMemoryEntry({
  longRunState,
  attentionSignal,
  campaignHandoff,
  deltaSinceLastResume,
}) {
  const sessionId = asText(longRunState?.long_run?.session_id || campaignHandoff?.session_id);
  if (!sessionId) {
    return null;
  }
  const checkpointId = asText(
    campaignHandoff?.last_checkpoint_id ||
      longRunState?.long_run?.latest_checkpoint_id ||
      longRunState?.long_run?.resume_from_checkpoint_id,
  );
  const packetId = asText(
    attentionSignal?.packet_id ||
      longRunState?.operator_guidance?.primary_cta?.attention_packet_id,
  );
  const attentionBlockingCount = asNumber(
    campaignHandoff?.attention_blocking_count ??
      attentionSignal?.blocking_count ??
      longRunState?.operator_guidance?.attention_inbox?.blocking_count,
    0,
  );
  const attentionInformationalCount = asNumber(
    campaignHandoff?.attention_informational_count ??
      attentionSignal?.informational_count ??
      longRunState?.operator_guidance?.attention_inbox?.informational_count,
    0,
  );
  const severity = asText(attentionSignal?.severity, attentionBlockingCount ? "blocking" : attentionInformationalCount ? "informational" : "clear");
  const currentBlocker = asText(
    campaignHandoff?.current_blocker ||
      longRunState?.operator_guidance?.blocking_reason ||
      longRunState?.long_run?.halt_reason,
  );
  const nextActionLabel = asText(
    campaignHandoff?.recommended_next_action_label ||
      longRunState?.operator_guidance?.primary_cta?.label,
  );
  const nextActionDetail = asText(
    campaignHandoff?.recommended_next_action_detail ||
      longRunState?.operator_guidance?.primary_cta?.detail,
  );
  const entryKey = [sessionId, checkpointId || "checkpoint:unknown", packetId || "packet:none", severity || "clear"].join("::");
  const summarySignature = [
    asText(campaignHandoff?.what_changed_summary),
    currentBlocker,
    nextActionLabel,
    asText(campaignHandoff?.next_stop_boundary_label),
    String(attentionBlockingCount),
    String(attentionInformationalCount),
  ].join("|");
  const now = new Date().toISOString();
  const active = attentionBlockingCount > 0 || attentionInformationalCount > 0;
  const initialLocalState = attentionBlockingCount > 0 || attentionInformationalCount > 0 ? "new" : "resolved";
  return normalizeHistoryEntry({
    entry_key: entryKey,
    session_id: sessionId,
    session_handle: asText(campaignHandoff?.session_handle || longRunState?.operator_guidance?.session_handle, sessionId.slice(-12) || sessionId),
    checkpoint_id: checkpointId,
    checkpoint_at: asText(campaignHandoff?.last_checkpoint_at || longRunState?.long_run?.last_checkpoint_at),
    lifecycle_state: asText(campaignHandoff?.lifecycle_state || longRunState?.long_run?.lifecycle_state),
    state_label: asText(campaignHandoff?.state_label || longRunState?.operator_guidance?.state_label),
    stop_reason: asText(longRunState?.long_run?.halt_reason || longRunState?.long_run?.completion_state),
    next_action_label: nextActionLabel,
    next_action_detail: nextActionDetail,
    what_changed_summary: asText(campaignHandoff?.what_changed_summary || deltaSinceLastResume?.summary),
    current_blocker: currentBlocker,
    next_stop_boundary_label: asText(
      campaignHandoff?.next_stop_boundary_label || longRunState?.operator_guidance?.next_stop_boundary_label,
    ),
    next_stop_boundary_summary: asText(
      campaignHandoff?.next_stop_boundary_summary || longRunState?.operator_guidance?.next_stop_boundary_summary,
    ),
    attention_blocking_count: attentionBlockingCount,
    attention_informational_count: attentionInformationalCount,
    current_cycle: asNumber(campaignHandoff?.current_cycle ?? longRunState?.long_run?.current_cycle, 0),
    max_cycles: asNumber(campaignHandoff?.max_cycles ?? longRunState?.long_run?.max_cycles, 0),
    checkpoint_count: asNumber(campaignHandoff?.checkpoint_count ?? longRunState?.long_run?.checkpoint_count, 0),
    severity,
    packet_id: packetId,
    state_family: asText(longRunState?.operator_guidance?.state_family),
    policy_headroom_summary: asText(
      campaignHandoff?.policy_headroom_summary || longRunState?.operator_guidance?.headroom_summary,
    ),
    settings_summary: asText(longRunState?.operator_guidance?.settings_summary),
    latest_progress_marker: asText(campaignHandoff?.latest_progress_marker),
    notification_candidate: severity === "blocking" && attentionBlockingCount > 0,
    local_state: initialLocalState,
    created_at: now,
    updated_at: now,
    active,
    continuation_resumed_after_packet: false,
    handoff_label: asText(campaignHandoff?.label, "Campaign handoff"),
    resume_ready_after_next_action: Boolean(campaignHandoff?.resume_ready_after_next_action),
    summary_signature: summarySignature,
  });
}

export function upsertHandoffMemory(memory, entry, options = {}) {
  const currentMemory = loadAttentionMemory(memory);
  if (!entry || !entry.session_id) {
    return {
      memory: currentMemory,
      sessionState: null,
      currentEntry: null,
      transition: "ignored",
      shouldNotify: false,
      notificationMode: currentNotificationMode(options.notificationSupport),
    };
  }
  const sessionId = asText(entry.session_id);
  const sessionState = clone(
    currentMemory.sessions?.[sessionId] || {
      current_entry_key: "",
      history: [],
    },
  );
  const normalizedEntry = normalizeHistoryEntry(entry);
  const existingIndex = sessionState.history.findIndex(
    (item) => asText(item?.entry_key) === normalizedEntry.entry_key,
  );
  const previousCurrent =
    sessionState.history.find(
      (item) => asText(item?.entry_key) === asText(sessionState.current_entry_key),
    ) || null;
  const now = new Date().toISOString();
  let shouldNotify = false;
  const notificationMode = currentNotificationMode(options.notificationSupport);

  if (existingIndex >= 0) {
    const existing = normalizeHistoryEntry(sessionState.history[existingIndex]);
    const resolved = !isBlockingEntry(normalizedEntry) && asNumber(normalizedEntry.attention_informational_count, 0) === 0;
    const merged = normalizeHistoryEntry({
      ...existing,
      ...normalizedEntry,
      created_at: existing.created_at || normalizedEntry.created_at || now,
      updated_at: now,
      seen_at: existing.seen_at || normalizedEntry.seen_at,
      acknowledged_at: existing.acknowledged_at || normalizedEntry.acknowledged_at,
      snoozed_until: existing.snoozed_until || normalizedEntry.snoozed_until,
      resolved_at: resolved ? existing.resolved_at || now : existing.resolved_at,
      local_state: resolved
        ? "resolved"
        : existing.local_state === "resolved" && normalizedEntry.local_state !== "resolved"
          ? normalizedEntry.local_state
          : existing.local_state || normalizedEntry.local_state,
      active: resolved ? false : normalizedEntry.active !== false,
      last_notified_at: existing.last_notified_at || normalizedEntry.last_notified_at,
    });
    sessionState.history.splice(existingIndex, 1, merged);
    sessionState.current_entry_key = merged.entry_key;
  } else {
    if (previousCurrent && previousCurrent.entry_key !== normalizedEntry.entry_key) {
      const previousIndex = sessionState.history.findIndex(
        (item) => asText(item?.entry_key) === previousCurrent.entry_key,
      );
      if (previousIndex >= 0) {
        const previousResolved = normalizeHistoryEntry({
          ...sessionState.history[previousIndex],
          active: false,
          resolved_at:
            !isBlockingEntry(sessionState.history[previousIndex]) ||
            !isBlockingEntry(normalizedEntry)
              ? now
              : sessionState.history[previousIndex]?.resolved_at,
          local_state:
            !isBlockingEntry(sessionState.history[previousIndex]) || !isBlockingEntry(normalizedEntry)
              ? "resolved"
              : sessionState.history[previousIndex]?.local_state,
          continuation_resumed_after_packet:
            !isBlockingEntry(sessionState.history[previousIndex]) || !isBlockingEntry(normalizedEntry),
        });
        sessionState.history.splice(previousIndex, 1, previousResolved);
      }
    }
    if (!isBlockingEntry(normalizedEntry) && asNumber(normalizedEntry.attention_informational_count, 0) === 0) {
      normalizedEntry.local_state = "resolved";
      normalizedEntry.resolved_at = normalizedEntry.resolved_at || now;
      normalizedEntry.active = false;
    }
    sessionState.history.unshift(normalizedEntry);
    sessionState.current_entry_key = normalizedEntry.entry_key;
    const transition = summarizeHandoffTransition(previousCurrent, normalizedEntry);
    const snoozedUntil = previousCurrent?.entry_key === normalizedEntry.entry_key ? previousCurrent?.snoozed_until : "";
    const snoozedActive = snoozedUntil && Date.parse(snoozedUntil) > Date.now();
    shouldNotify =
      notificationMode === "browser" &&
      normalizedEntry.notification_candidate &&
      !snoozedActive &&
      transition !== "unchanged";
    if (shouldNotify) {
      normalizedEntry.last_notified_at = now;
      sessionState.history[0] = normalizedEntry;
    }
  }

  sessionState.history = sessionState.history
    .map((item) => normalizeHistoryEntry(item))
    .slice(0, HISTORY_LIMIT);
  currentMemory.sessions = {
    ...currentMemory.sessions,
    [sessionId]: sessionState,
  };
  const currentEntry =
    sessionState.history.find(
      (item) => asText(item?.entry_key) === asText(sessionState.current_entry_key),
    ) || null;
  return {
    memory: currentMemory,
    sessionState,
    currentEntry,
    transition: summarizeHandoffTransition(previousCurrent, currentEntry),
    shouldNotify,
    notificationMode,
  };
}

export function markHandoffEntryState(memory, sessionId, entryKey, nextState, options = {}) {
  const currentMemory = loadAttentionMemory(memory);
  const normalizedSessionId = asText(sessionId);
  const targetKey = asText(entryKey);
  const sessionState = currentMemory.sessions?.[normalizedSessionId];
  if (!sessionState) {
    return {
      memory: currentMemory,
      sessionState: null,
      currentEntry: null,
    };
  }
  const now = new Date().toISOString();
  const snoozeMinutes = asNumber(options.snoozeMinutes, DEFAULT_SNOOZE_MINUTES);
  const history = (sessionState.history || []).map((item) => {
    const normalized = normalizeHistoryEntry(item);
    if (normalized.entry_key !== targetKey) {
      return normalized;
    }
    if (nextState === "seen") {
      normalized.local_state = "seen";
      normalized.seen_at = normalized.seen_at || now;
    } else if (nextState === "acknowledged") {
      normalized.local_state = "acknowledged";
      normalized.seen_at = normalized.seen_at || now;
      normalized.acknowledged_at = now;
    } else if (nextState === "resolved") {
      normalized.local_state = "resolved";
      normalized.resolved_at = now;
      normalized.active = false;
    } else if (nextState === "snoozed") {
      normalized.local_state = "snoozed";
      normalized.seen_at = normalized.seen_at || now;
      normalized.snoozed_until = new Date(Date.now() + snoozeMinutes * 60 * 1000).toISOString();
    }
    normalized.updated_at = now;
    return normalized;
  });
  currentMemory.sessions = {
    ...currentMemory.sessions,
    [normalizedSessionId]: {
      ...sessionState,
      history,
    },
  };
  const currentEntry =
    history.find((item) => asText(item?.entry_key) === asText(sessionState.current_entry_key)) || null;
  return {
    memory: currentMemory,
    sessionState: currentMemory.sessions[normalizedSessionId],
    currentEntry,
  };
}

export function summarizeCurrentSessionMemory(memory, sessionId) {
  const currentMemory = loadAttentionMemory(memory);
  const normalizedSessionId = asText(sessionId);
  const sessionState = currentMemory.sessions?.[normalizedSessionId];
  const history = Array.isArray(sessionState?.history) ? sessionState.history.map(normalizeHistoryEntry) : [];
  const currentEntry =
    history.find((item) => asText(item?.entry_key) === asText(sessionState?.current_entry_key)) || history[0] || null;
  const blockingActive = history.filter((item) => item.active && isBlockingEntry(item));
  const resolved = history.filter((item) => isResolvedEntry(item));
  const latestResolved = resolved[0] || null;
  return {
    currentEntry,
    history,
    unreadBlockingCount: blockingActive.filter((item) => item.local_state === "new").length,
    acknowledgedBlockingCount: blockingActive.filter((item) => item.local_state === "acknowledged").length,
    seenBlockingCount: blockingActive.filter((item) => item.local_state === "seen" || item.local_state === "snoozed").length,
    staleBlockingCount: blockingActive.filter((item) => classifyAttentionArchiveState(item) === "stale_escalated_blocking").length,
    unresolvedBlockingCount: blockingActive.length,
    resolvedCount: resolved.length,
    latestResolved,
  };
}

export function buildSafeNotificationContent(entry) {
  const sessionHandle = asText(entry?.session_handle, "current session");
  const archiveState = classifyAttentionArchiveState(entry);
  const severityLabel =
    archiveState === "stale_escalated_blocking"
      ? "Stale blocking attention"
      : asText(entry?.severity) === "blocking"
        ? "Blocking attention required"
      : asText(entry?.severity) === "informational"
        ? "Session update available"
        : "Session update";
  const attentionCategory =
    archiveState === "stale_escalated_blocking"
      ? "stale escalated"
      : archiveState === "acknowledged_unresolved_blocking"
        ? "acknowledged unresolved"
        : archiveState === "seen_unresolved_blocking"
          ? "seen unresolved"
          : archiveState === "new_blocking"
            ? "new blocking"
            : "session update";
  const reason = asText(entry?.current_blocker, "review current handoff");
  const nextActionLabel = asText(entry?.next_action_label, "Open workspace");
  return {
    title: `${sessionHandle}: ${severityLabel}`,
    body: `${attentionCategory}. ${reason}. Next action: ${nextActionLabel}.`,
  };
}
