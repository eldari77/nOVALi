const BLOCKING_BUCKETS = new Set([
  "new_blocking_now",
  "stale_escalated_blocking",
  "seen_unresolved_blocking",
  "acknowledged_unresolved_blocking",
]);
const REVIEW_ACTION_PATTERN = /review|approve|resolve|intervention|packet|gate/i;
const DIGEST_LIST_LIMIT = 3;
const MANAGER_ITEM_EVENT_LIMIT = 12;
const MANAGER_SNOOZE_NEXT_CHECK_KEY = "next_manager_check";
const MANAGER_SNOOZE_NEXT_CHECK_LABEL = "Snoozed until next manager check";
const MANAGER_SNOOZE_UNTIL_REOPEN_KEY = "until_reopen";
const MANAGER_SNOOZE_UNTIL_REOPEN_LABEL = "Deferred until reopened";
const MANAGER_RETURN_REASON_NEXT_CHECK = "due_next_manager_check";
const MANAGER_RETURN_REASON_MANUAL_REOPEN = "manual_reopen";
const DEFERRED_PRESSURE_LOW_KEY = "low";
const DEFERRED_PRESSURE_RISING_KEY = "rising";
const DEFERRED_PRESSURE_HIGH_KEY = "high";
const RESPONSE_OUTCOME_IMPROVED_KEY = "improved";
const RESPONSE_OUTCOME_STABLE_KEY = "stable";
const RESPONSE_OUTCOME_WORSENED_KEY = "worsened";

export const PORTFOLIO_OPERATOR_QUEUE_GROUPS = [
  {
    key: "pending_review_intervention",
    label: "Pending review / intervention",
    tone: "warning",
    detail:
      "These sessions are stopped on explicit operator review or intervention work and remain the clearest shell-level action path.",
  },
  {
    key: "stale_escalated",
    label: "Stale escalated",
    tone: "danger",
    detail:
      "Already-seen unresolved blockers have aged into a higher local prominence without changing backend blocking truth.",
  },
  {
    key: "blocking_now",
    label: "Blocking now",
    tone: "warning",
    detail:
      "These sessions currently need operator attention even when they are not yet stale or review-specific.",
  },
  {
    key: "resumable",
    label: "Resumable sessions",
    tone: "success",
    detail:
      "These sessions are ready for an operator choice to continue the same bounded lineage.",
  },
  {
    key: "running_waiting",
    label: "Running / waiting inside bounds",
    tone: "info",
    detail:
      "These sessions are progressing or waiting inside their current bounded posture and are generally safe to ignore briefly.",
  },
  {
    key: "completed_halted",
    label: "Completed / halted",
    tone: "phase",
    detail:
      "These sessions remain reviewable but do not currently compete with active operator work.",
  },
  {
    key: "archived_informational",
    label: "Archived / informational",
    tone: "phase",
    detail:
      "These cards remain bounded history or low-priority context and are the safest shell-level items to defer.",
  },
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

function sortCards(left, right) {
  return (
    asNumber(left?.queue_rank, 0) - asNumber(right?.queue_rank, 0) ||
    parseDateMs(right?.updated_at || right?.checkpoint_at || right?.lifecycle_updated_at) -
      parseDateMs(left?.updated_at || left?.checkpoint_at || left?.lifecycle_updated_at) ||
    asText(left?.session_handle || left?.session_id).localeCompare(
      asText(right?.session_handle || right?.session_id),
    )
  );
}

function hasBlockingBucket(cardOrEntry) {
  return BLOCKING_BUCKETS.has(asText(cardOrEntry?.queue_bucket));
}

function isReviewInterventionCard(card) {
  const actionText = [
    asText(card?.shortcut_action_label),
    asText(card?.shortcut_action_detail),
    asText(card?.next_action_label),
    asText(card?.next_action_detail),
    asText(card?.recommended_next_action_label),
    asText(card?.recommended_next_action_detail),
    asText(card?.current_blocker),
  ]
    .join(" ")
    .trim();
  return REVIEW_ACTION_PATTERN.test(actionText);
}

function safeProgressMarker(card) {
  return (
    asText(card?.what_changed_summary) ||
    asText(card?.latest_progress_marker) ||
    asText(card?.current_blocker) ||
    asText(card?.shortcut_action_detail) ||
    "No additional bounded delta was summarized for this shell view."
  );
}

function operatorActionLabel(cardOrEntry) {
  return asText(
    cardOrEntry?.shortcut_action_label ||
      cardOrEntry?.next_action_label ||
      cardOrEntry?.recommended_next_action_label,
  );
}

function snapshotEntryFromCard(card) {
  return {
    session_id: asText(card?.session_id),
    entry_key: asText(card?.entry_key),
    session_handle: asText(card?.session_handle),
    queue_bucket: asText(card?.queue_bucket, "clear"),
    operator_queue_group: classifyOperatorQueueGroup(card),
    lifecycle_state: asText(card?.lifecycle_state),
    lifecycle_section: asText(card?.lifecycle_section),
    checkpoint_id: asText(card?.checkpoint_id),
    checkpoint_count: asNumber(card?.checkpoint_count, 0),
    current_cycle: asNumber(card?.current_cycle, 0),
    summary_signature: asText(card?.summary_signature),
    next_action_label: operatorActionLabel(card),
    current_blocker: asText(card?.current_blocker),
    latest_progress_marker: asText(card?.latest_progress_marker),
    what_changed_summary: asText(card?.what_changed_summary),
    archived: Boolean(card?.archived),
    pinned: Boolean(card?.pinned),
    shortlisted: Boolean(card?.shortlisted),
  };
}

function buildSnapshotMap(snapshot) {
  return new Map(
    (Array.isArray(snapshot?.sessions) ? snapshot.sessions : [])
      .filter((entry) => asText(entry?.session_id))
      .map((entry) => [asText(entry.session_id), entry]),
  );
}

function digestLine(card, summary) {
  const handle = asText(card?.session_handle || card?.session_id, "session");
  return `${handle}: ${summary}`;
}

function pluralize(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function recommendationShortlist(recommendation) {
  return (Array.isArray(recommendation?.shortlist) ? recommendation.shortlist : [])
    .filter(Boolean)
    .slice(0, DIGEST_LIST_LIMIT);
}

function normalizeManagerItemMemoryEntry(sessionId, entry) {
  const resolvedSessionId = asText(entry?.session_id || sessionId);
  if (!resolvedSessionId) {
    return null;
  }
  return {
    session_id: resolvedSessionId,
    session_handle: asText(entry?.session_handle || resolvedSessionId, "session"),
    current_blocker: asText(entry?.current_blocker),
    next_action_label: asText(entry?.next_action_label),
    summary_signature: asText(entry?.summary_signature),
    deferred_at: asText(entry?.deferred_at),
    defer_basis_key: asText(entry?.defer_basis_key),
    defer_basis_label: asText(entry?.defer_basis_label),
    reopened_at: asText(entry?.reopened_at),
    return_reason: asText(entry?.return_reason),
    active: Boolean(entry?.active),
  };
}

function normalizeManagerItemEvent(event) {
  const sessionId = asText(event?.session_id);
  if (!sessionId) {
    return null;
  }
  return {
    session_id: sessionId,
    session_handle: asText(event?.session_handle || sessionId, "session"),
    event_type: asText(event?.event_type),
    at: asText(event?.at),
    basis_key: asText(event?.basis_key),
    basis_label: asText(event?.basis_label),
    next_action_label: asText(event?.next_action_label),
    current_blocker: asText(event?.current_blocker),
    return_reason: asText(event?.return_reason),
  };
}

function trimManagerItemEvents(events) {
  return (Array.isArray(events) ? events : [])
    .map(normalizeManagerItemEvent)
    .filter(Boolean)
    .sort((left, right) => parseDateMs(right?.at) - parseDateMs(left?.at))
    .slice(0, MANAGER_ITEM_EVENT_LIMIT);
}

function managerItemMemoryFromRaw(raw) {
  return Object.fromEntries(
    Object.entries(raw && typeof raw === "object" ? raw : {})
      .map(([sessionId, entry]) => {
        const normalized = normalizeManagerItemMemoryEntry(sessionId, entry);
        return normalized ? [normalized.session_id, normalized] : null;
      })
      .filter(Boolean),
  );
}

function buildDeferredManagerItemEntry(card, options = {}) {
  return normalizeManagerItemMemoryEntry(asText(card?.session_id), {
    session_id: asText(card?.session_id),
    session_handle: asText(card?.session_handle || card?.session_id, "session"),
    current_blocker: asText(card?.current_blocker),
    next_action_label: operatorActionLabel(card),
    summary_signature: asText(card?.summary_signature),
    deferred_at: asText(options.deferredAt || new Date().toISOString()),
    defer_basis_key: asText(options.deferBasisKey || MANAGER_SNOOZE_NEXT_CHECK_KEY),
    defer_basis_label: asText(options.deferBasisLabel || MANAGER_SNOOZE_NEXT_CHECK_LABEL),
    reopened_at: "",
    return_reason: "",
    active: true,
  });
}

function isManagerItemDeferred(entry) {
  return Boolean(entry?.active) && asText(entry?.deferred_at);
}

function deferBasisStillActive(entry, anchorRecordedAt) {
  if (!isManagerItemDeferred(entry)) {
    return false;
  }
  if (asText(entry?.defer_basis_key) !== MANAGER_SNOOZE_NEXT_CHECK_KEY) {
    return Boolean(entry?.active);
  }
  const deferredAtMs = parseDateMs(entry?.deferred_at);
  const anchorMs = parseDateMs(anchorRecordedAt);
  return !(anchorMs > deferredAtMs);
}

function managerItemReopenedSince(entry, anchorRecordedAt) {
  const reopenedAtMs = parseDateMs(entry?.reopened_at);
  if (!reopenedAtMs) {
    return false;
  }
  const anchorMs = parseDateMs(anchorRecordedAt);
  return anchorMs ? reopenedAtMs >= anchorMs : true;
}

function managerReturnReasonLabel(entry) {
  const returnReason = asText(entry?.return_reason);
  if (returnReason === MANAGER_RETURN_REASON_NEXT_CHECK) {
    return "Returned because the next manager check came due";
  }
  if (returnReason === MANAGER_RETURN_REASON_MANUAL_REOPEN) {
    return "Returned because the operator reopened it manually";
  }
  return "";
}

function agendaStatePriority(card) {
  switch (asText(card?.agenda_state_key)) {
    case "overdue_after_return":
      return 0;
    case "overdue_manager_item":
      return 1;
    case "due_return_now":
      return 2;
    case "reopened_after_defer":
      return 3;
    case "new_since_last_check":
      return 4;
    case "reviewed_still_pending":
      return 5;
    case "deferred_until_next_manager_check":
      return 6;
    case "deferred_until_reopen":
      return 7;
    default:
      return 20;
  }
}

function agendaTimingMs(card) {
  return (
    parseDateMs(card?.manager_reopened_at) ||
    parseDateMs(card?.manager_deferred_at) ||
    parseDateMs(card?.updated_at || card?.checkpoint_at || card?.lifecycle_updated_at)
  );
}

function isDeferredRelatedAgendaState(key) {
  return [
    "deferred_until_next_manager_check",
    "deferred_until_reopen",
    "due_return_now",
    "reopened_after_defer",
    "overdue_after_return",
  ].includes(asText(key));
}

function dedupeCardsBySessionId(cards = []) {
  const seen = new Set();
  return (Array.isArray(cards) ? cards : []).filter((card) => {
    const sessionId = asText(card?.session_id);
    if (!sessionId || seen.has(sessionId)) {
      return false;
    }
    seen.add(sessionId);
    return true;
  });
}

function buildDeferredPressureBand(options = {}) {
  const totalDeferredItems = asNumber(options.totalDeferredItems, 0);
  const dueNow = asNumber(options.dueNow, 0);
  const overdueAfterReturn = asNumber(options.overdueAfterReturn, 0);
  const reopenedManually = asNumber(options.reopenedManually, 0);
  const deferredSinceLastCheck = asNumber(options.deferredSinceLastCheck, 0);
  const dueReturnedSinceLastCheck = asNumber(options.dueReturnedSinceLastCheck, 0);
  const reopenedSinceLastCheck = asNumber(options.reopenedSinceLastCheck, 0);
  const overdueAfterReturnSinceLastCheck = asNumber(options.overdueAfterReturnSinceLastCheck, 0);
  const deferredCompletedSinceLastCheck = asNumber(options.deferredCompletedSinceLastCheck, 0);

  let key = DEFERRED_PRESSURE_LOW_KEY;
  let label = "Low deferred pressure";
  let detail =
    totalDeferredItems > 0
      ? "Deferred pressure is low; parked deferred backlog exists, but no due-now item is competing with the active agenda."
      : "Deferred pressure is low; no deferred item is competing with current blockers.";

  if (overdueAfterReturn > 0 || dueNow >= 2) {
    key = DEFERRED_PRESSURE_HIGH_KEY;
    label = "High deferred pressure";
    if (overdueAfterReturn > 0) {
      detail = `Deferred pressure is high because ${pluralize(
        overdueAfterReturn,
        "returned item",
        "returned items",
      )} are overdue after return${dueNow > 0 ? ` and ${pluralize(dueNow, "more item", "more items")} are due now` : ""}.`;
    } else {
      detail = `Deferred pressure is high because ${pluralize(
        dueNow,
        "due-now item",
        "due-now items",
      )} are competing with current blockers at once.`;
    }
  } else if (
    dueNow > 0 ||
    reopenedManually > 0 ||
    dueReturnedSinceLastCheck > 0 ||
    reopenedSinceLastCheck > 0 ||
    overdueAfterReturnSinceLastCheck > 0
  ) {
    key = DEFERRED_PRESSURE_RISING_KEY;
    label = "Rising deferred pressure";
    if (overdueAfterReturnSinceLastCheck > 0) {
      detail = `Deferred pressure is rising because ${pluralize(
        overdueAfterReturnSinceLastCheck,
        "returned item",
        "returned items",
      )} crossed into overdue-after-return after the latest manager check.`;
    } else if (dueNow > 0 && reopenedManually > 0) {
      detail = `Deferred pressure is rising because ${pluralize(
        dueNow,
        "due-now item",
        "due-now items",
      )} returned from the deferred queue while ${pluralize(
        reopenedManually,
        "manually reopened item",
        "manually reopened items",
      )} also remain active.`;
    } else if (dueNow > 0) {
      detail = `Deferred pressure is rising because ${pluralize(
        dueNow,
        "item",
      )} ${dueNow === 1 ? "is" : "are"} due now after the latest manager check.`;
    } else {
      detail = `Deferred pressure is rising because ${pluralize(
        reopenedManually,
        "item",
      )} ${reopenedManually === 1 ? "is" : "are"} active through manual reopen.`;
    }
  } else if (deferredCompletedSinceLastCheck > 0 && deferredSinceLastCheck === 0) {
    detail =
      totalDeferredItems > 0
        ? `Deferred pressure is low; ${pluralize(
            deferredCompletedSinceLastCheck,
            "deferred item",
          )} completed since the last manager check and the remaining backlog is still parked.`
        : `Deferred pressure is low; ${pluralize(
            deferredCompletedSinceLastCheck,
            "deferred item",
          )} completed since the last manager check and no deferred item is competing now.`;
  }

  const upwardPressure =
    deferredSinceLastCheck +
    dueReturnedSinceLastCheck +
    reopenedSinceLastCheck +
    overdueAfterReturnSinceLastCheck;
  let trendKey = "stable";
  let trendLabel = "Pressure stable";
  if (upwardPressure > deferredCompletedSinceLastCheck) {
    trendKey = "increased";
    trendLabel = "Pressure increased";
  } else if (deferredCompletedSinceLastCheck > upwardPressure) {
    trendKey = "decreased";
    trendLabel = "Pressure decreased";
  }

  return {
    key,
    label,
    detail,
    trendKey,
    trendLabel,
  };
}

function buildDeferredResponsePolicy(options = {}) {
  const pressureBand = options.pressureBand || {};
  const totalDeferredItems = asNumber(options.totalDeferredItems, 0);
  const deferredNotYetDue = asNumber(options.deferredNotYetDue, 0);
  const dueNow = asNumber(options.dueNow, 0);
  const overdueAfterReturn = asNumber(options.overdueAfterReturn, 0);
  const reopenedManually = asNumber(options.reopenedManually, 0);
  const nextManagerCheckCount = asNumber(options.nextManagerCheckCount, 0);
  const untilReopenCount = asNumber(options.untilReopenCount, 0);

  let primary = null;
  const shortlist = [];

  if (asText(pressureBand.key) === DEFERRED_PRESSURE_HIGH_KEY) {
    primary =
      overdueAfterReturn > 0
        ? {
            key: "review_overdue_after_return",
            label: "Review overdue-after-return items before taking on new deferred work",
            detail: `${pluralize(
              overdueAfterReturn,
              "returned item",
              "returned items",
            )} stayed unresolved after returning and now outrank newly due deferred work.`,
          }
        : {
            key: "clear_due_now_first",
            label: "Deferred pressure is high; clear due-now items first",
            detail: `${pluralize(
              dueNow,
              "due-now item",
              "due-now items",
            )} are already competing with current blockers.`,
          };
    if (reopenedManually > 0) {
      shortlist.push({
        key: "manual_reopen_mix",
        label: "Manual reopen is accumulating; decide whether to reopen or keep parked",
        detail: `${pluralize(reopenedManually, "item")} ${
          reopenedManually === 1 ? "is" : "are"
        } active through manual reopen.`,
      });
    }
    shortlist.push({
      key: "archive_safe_noise",
      label: "Archive safe informational noise, not blockers",
      detail:
        "Archive only safe informational clutter; keep true blockers and due deferred work visible.",
    });
  } else if (asText(pressureBand.key) === DEFERRED_PRESSURE_RISING_KEY) {
    if (dueNow > 0) {
      primary = {
        key: "clear_due_now_first",
        label: "Deferred pressure is rising; clear due-now items first",
        detail: `${pluralize(
          dueNow,
          "due-now item",
          "due-now items",
        )} returned from the deferred queue and now compete with the active agenda.`,
      };
    } else {
      primary = {
        key: "review_manual_reopen_mix",
        label: "Manual reopen is accumulating; decide whether to reopen or keep parked",
        detail: `${pluralize(reopenedManually, "item")} ${
          reopenedManually === 1 ? "is" : "are"
        } active because the operator reopened ${reopenedManually === 1 ? "it" : "them"} manually.`,
      };
    }
    if (reopenedManually > 0 && dueNow > 0) {
      shortlist.push({
        key: "manual_reopen_mix",
        label: "Manual reopen is accumulating; decide whether to reopen or keep parked",
        detail: `${pluralize(reopenedManually, "item")} ${
          reopenedManually === 1 ? "is" : "are"
        } active because the operator reopened ${reopenedManually === 1 ? "it" : "them"} manually.`,
      });
    }
    if (deferredNotYetDue > 0) {
      shortlist.push({
        key: "avoid_new_deferred_work",
        label: "Avoid adding more deferred work until due items are clearer",
        detail: `${pluralize(deferredNotYetDue, "item")} ${
          deferredNotYetDue === 1 ? "remains" : "remain"
        } parked in backlog behind the active agenda.`,
      });
    }
  } else {
    primary = {
      key: "continue_current_work",
      label: "Normal deferred backlog; continue current work",
      detail:
        totalDeferredItems > 0
          ? "No due-now or overdue-after-return deferred item is competing with current blockers right now."
          : "No deferred item currently needs a special shell-level response.",
    };
    if (untilReopenCount > 0) {
      shortlist.push({
        key: "keep_manual_backlog_parked",
        label: "Keep manual-reopen backlog parked until it truly deserves active review",
        detail: `${pluralize(untilReopenCount, "item")} ${
          untilReopenCount === 1 ? "is" : "are"
        } waiting on explicit reopen.`,
      });
    }
    if (nextManagerCheckCount > 0) {
      shortlist.push({
        key: "watch_next_check_returns",
        label: "Watch the next manager check for automatic returns",
        detail: `${pluralize(nextManagerCheckCount, "item")} ${
          nextManagerCheckCount === 1 ? "is" : "are"
        } parked until the next explicit manager check.`,
      });
    }
  }

  let detail = "No deferred response is needed right now.";
  if (nextManagerCheckCount > untilReopenCount && nextManagerCheckCount > 0) {
    detail =
      "Automatic next-manager-check returns are driving more of the current deferred pressure than manual reopen backlog.";
  } else if (untilReopenCount > nextManagerCheckCount && untilReopenCount > 0) {
    detail =
      "Manual-reopen backlog is driving more of the current deferred pressure than automatic next-manager-check returns.";
  } else if (nextManagerCheckCount > 0 && untilReopenCount > 0) {
    detail =
      "Deferred pressure is mixed between automatic next-manager-check returns and manual reopen backlog.";
  } else if (reopenedManually > 0) {
    detail =
      "Current deferred pressure is being carried by manually reopened items that remain active.";
  }

  const seen = new Set();
  const boundedShortlist = shortlist
    .filter((item) => {
      const key = asText(item?.key);
      if (!key || seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    })
    .slice(0, DIGEST_LIST_LIMIT);

  return {
    primary,
    shortlist: boundedShortlist,
    detail,
  };
}

function pressureBandRank(key) {
  switch (asText(key)) {
    case DEFERRED_PRESSURE_HIGH_KEY:
      return 2;
    case DEFERRED_PRESSURE_RISING_KEY:
      return 1;
    default:
      return 0;
  }
}

function normalizeDeferredStateSnapshot(raw, fallbackRecordedAt = "") {
  if (!raw || typeof raw !== "object") {
    return null;
  }
  const recordedAt = asText(raw.recorded_at || fallbackRecordedAt);
  const pressureBandKey = asText(raw.pressure_band_key);
  return {
    recorded_at: recordedAt,
    pressure_band_key: pressureBandKey,
    pressure_band_label: asText(
      raw.pressure_band_label,
      pressureBandKey ? `${pressureBandKey} deferred pressure` : "",
    ),
    due_now: asNumber(raw.due_now, 0),
    overdue_after_return: asNumber(raw.overdue_after_return, 0),
    reopened_manually: asNumber(raw.reopened_manually, 0),
    total_deferred_items: asNumber(raw.total_deferred_items, 0),
    deferred_not_yet_due: asNumber(raw.deferred_not_yet_due, 0),
    return_basis_next_manager_check: asNumber(raw.return_basis_next_manager_check, 0),
    return_basis_until_reopen: asNumber(raw.return_basis_until_reopen, 0),
    recommended_response_key: asText(raw.recommended_response_key),
    recommended_response_label: asText(raw.recommended_response_label),
    recommended_response_detail: asText(raw.recommended_response_detail),
    pressure_detail: asText(raw.pressure_detail),
    current_reason: asText(raw.current_reason),
    source: asText(raw.source),
    target_session_id: asText(raw.target_session_id),
    action_label: asText(raw.action_label),
  };
}

export function buildDeferredResponseAnchorState(digest = null, options = {}) {
  const counts = digest?.counts || {};
  return normalizeDeferredStateSnapshot(
    {
      recorded_at: asText(options.recordedAt || new Date().toISOString()),
      pressure_band_key: asText(digest?.pressureBand?.key),
      pressure_band_label: asText(digest?.pressureBand?.label),
      due_now: asNumber(counts.due_now, 0),
      overdue_after_return: asNumber(counts.overdue_after_return, 0),
      reopened_manually: asNumber(counts.reopened_manually, 0),
      total_deferred_items: asNumber(counts.total_deferred_items, 0),
      deferred_not_yet_due: asNumber(counts.deferred_not_yet_due, 0),
      return_basis_next_manager_check: asNumber(counts.return_basis_next_manager_check, 0),
      return_basis_until_reopen: asNumber(counts.return_basis_until_reopen, 0),
      recommended_response_key: asText(digest?.responsePolicy?.primary?.key),
      recommended_response_label: asText(digest?.responsePolicy?.primary?.label),
      recommended_response_detail: asText(digest?.responsePolicy?.primary?.detail),
      pressure_detail: asText(digest?.detail),
      current_reason: asText(digest?.currentReason),
      source: asText(options.source),
      target_session_id: asText(options.targetSessionId),
      action_label: asText(options.actionLabel),
    },
    asText(options.recordedAt),
  );
}

function buildDeferredResponseOutcome(options = {}) {
  const previousState = normalizeDeferredStateSnapshot(
    options.previousState,
    asText(options.recordedAt),
  );
  if (!previousState) {
    return null;
  }

  const currentPressureBand = options.currentPressureBand || {};
  const currentResponsePolicy = options.currentResponsePolicy || {};
  const currentCounts = options.currentCounts || {};
  const currentBandKey = asText(currentPressureBand.key, DEFERRED_PRESSURE_LOW_KEY);
  const currentBandLabel = asText(currentPressureBand.label, "Low deferred pressure");
  const currentDueNow = asNumber(currentCounts.due_now, 0);
  const currentOverdueAfterReturn = asNumber(currentCounts.overdue_after_return, 0);
  const currentReopenedManually = asNumber(currentCounts.reopened_manually, 0);
  const currentTotalDeferred = asNumber(currentCounts.total_deferred_items, 0);

  const previousBandRank = pressureBandRank(previousState.pressure_band_key);
  const currentBandRank = pressureBandRank(currentBandKey);
  const dueDelta = currentDueNow - asNumber(previousState.due_now, 0);
  const overdueDelta = currentOverdueAfterReturn - asNumber(previousState.overdue_after_return, 0);
  const reopenedDelta = currentReopenedManually - asNumber(previousState.reopened_manually, 0);
  const totalDeferredDelta = currentTotalDeferred - asNumber(previousState.total_deferred_items, 0);

  let key = RESPONSE_OUTCOME_STABLE_KEY;
  let label = "Response outcome stable";
  let detail = "";

  if (overdueDelta < 0) {
    key = RESPONSE_OUTCOME_IMPROVED_KEY;
    label = "Response outcome improved";
    detail = `Deferred pressure improved: overdue-after-return items fell from ${asNumber(previousState.overdue_after_return, 0)} to ${currentOverdueAfterReturn}.`;
  } else if (overdueDelta > 0) {
    key = RESPONSE_OUTCOME_WORSENED_KEY;
    label = "Response outcome worsened";
    detail = `Deferred pressure worsened: overdue-after-return items rose from ${asNumber(previousState.overdue_after_return, 0)} to ${currentOverdueAfterReturn}.`;
  } else if (currentBandRank < previousBandRank) {
    key = RESPONSE_OUTCOME_IMPROVED_KEY;
    label = "Response outcome improved";
    detail = `Deferred pressure improved: the pressure band moved from ${asText(previousState.pressure_band_label, "the prior band")} to ${currentBandLabel}.`;
  } else if (currentBandRank > previousBandRank) {
    key = RESPONSE_OUTCOME_WORSENED_KEY;
    label = "Response outcome worsened";
    detail = `Deferred pressure worsened: the pressure band moved from ${asText(previousState.pressure_band_label, "the prior band")} to ${currentBandLabel}.`;
  } else if (dueDelta < 0) {
    key = RESPONSE_OUTCOME_IMPROVED_KEY;
    label = "Response outcome improved";
    detail = `Deferred pressure improved: due-now items fell from ${asNumber(previousState.due_now, 0)} to ${currentDueNow}.`;
  } else if (dueDelta > 0) {
    key = RESPONSE_OUTCOME_WORSENED_KEY;
    label = "Response outcome worsened";
    detail = `Deferred pressure worsened: due-now items rose from ${asNumber(previousState.due_now, 0)} to ${currentDueNow}.`;
  } else if (reopenedDelta < 0) {
    key = RESPONSE_OUTCOME_IMPROVED_KEY;
    label = "Response outcome improved";
    detail = `Deferred pressure improved: manually reopened items fell from ${asNumber(previousState.reopened_manually, 0)} to ${currentReopenedManually}.`;
  } else if (reopenedDelta > 0) {
    key = RESPONSE_OUTCOME_WORSENED_KEY;
    label = "Response outcome worsened";
    detail = `Deferred pressure worsened: manually reopened items rose from ${asNumber(previousState.reopened_manually, 0)} to ${currentReopenedManually}.`;
  } else if (totalDeferredDelta < 0) {
    key = RESPONSE_OUTCOME_IMPROVED_KEY;
    label = "Response outcome improved";
    detail = `Deferred pressure improved: total deferred workload fell from ${asNumber(previousState.total_deferred_items, 0)} to ${currentTotalDeferred}.`;
  } else if (totalDeferredDelta > 0) {
    key = RESPONSE_OUTCOME_WORSENED_KEY;
    label = "Response outcome worsened";
    detail = `Deferred pressure worsened: total deferred workload rose from ${asNumber(previousState.total_deferred_items, 0)} to ${currentTotalDeferred}.`;
  } else if (currentOverdueAfterReturn > 0) {
    detail = `Deferred pressure persisted: ${pluralize(currentOverdueAfterReturn, "overdue-after-return item", "overdue-after-return items")} remain unresolved.`;
  } else if (currentDueNow > 0) {
    detail = `Deferred pressure persisted: ${pluralize(currentDueNow, "due-now item", "due-now items")} still compete with the active agenda.`;
  } else if (currentTotalDeferred > 0) {
    detail = `Deferred pressure persisted: ${pluralize(currentTotalDeferred, "deferred item")} remain parked or active without changing the current pressure band.`;
  } else {
    detail = "Deferred pressure remained stable with no deferred workload currently in play.";
  }

  const basisKey =
    asText(previousState.source) === "shell_action"
      ? "since_last_suggested_response"
      : "since_last_manager_check";

  return {
    key,
    label,
    detail,
    basisKey,
    basisLabel:
      basisKey === "since_last_suggested_response"
        ? "Since last suggested response"
        : "Since last manager check",
    actedSinceAnchor: asText(previousState.source) === "shell_action",
    actionDetail:
      asText(previousState.source) === "shell_action"
        ? `The last suggested shell response was ${asText(
            previousState.action_label || previousState.recommended_response_label,
            "acted on",
          )}.`
        : "No shell-guided action is recorded for this comparison, so the outcome reflects pressure drift since the last manager check.",
    previousBandKey: asText(previousState.pressure_band_key),
    previousBandLabel: asText(previousState.pressure_band_label),
    currentBandKey,
    currentBandLabel,
    previousResponseKey: asText(previousState.recommended_response_key),
    previousResponseLabel: asText(previousState.recommended_response_label),
    currentResponseKey: asText(currentResponsePolicy?.primary?.key),
    currentResponseLabel: asText(currentResponsePolicy?.primary?.label),
    deltas: {
      due_now: dueDelta,
      overdue_after_return: overdueDelta,
      reopened_manually: reopenedDelta,
      total_deferred_items: totalDeferredDelta,
    },
  };
}

function sortAgendaCards(left, right) {
  return (
    agendaStatePriority(left) - agendaStatePriority(right) ||
    agendaTimingMs(left) - agendaTimingMs(right) ||
    sortCards(left, right)
  );
}

export function createEmptyPortfolioDigestMemory() {
  return {
    schema_version: 4,
    last_manager_check_at: "",
    last_manager_check_snapshot: null,
    last_manager_touch_at: "",
    last_manager_touch_snapshot: null,
    last_deferred_response_anchor: null,
    manager_items: {},
    manager_item_events: [],
  };
}

export function loadPortfolioDigestMemory(raw) {
  if (!raw) {
    return createEmptyPortfolioDigestMemory();
  }
  try {
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!parsed || typeof parsed !== "object") {
      return createEmptyPortfolioDigestMemory();
    }
    return {
      schema_version: 4,
      last_manager_check_at: asText(parsed.last_manager_check_at || parsed.last_manager_touch_at),
      last_manager_check_snapshot:
        (parsed.last_manager_check_snapshot && typeof parsed.last_manager_check_snapshot === "object"
          ? {
              recorded_at: asText(parsed.last_manager_check_snapshot.recorded_at),
              session_count: asNumber(parsed.last_manager_check_snapshot.session_count, 0),
              recommendation_label: asText(parsed.last_manager_check_snapshot.recommendation_label),
              deferred_state: normalizeDeferredStateSnapshot(
                parsed.last_manager_check_snapshot.deferred_state,
                asText(parsed.last_manager_check_snapshot.recorded_at),
              ),
              sessions: Array.isArray(parsed.last_manager_check_snapshot.sessions)
                ? parsed.last_manager_check_snapshot.sessions.map((entry) => ({
                    ...snapshotEntryFromCard(entry),
                  }))
                : [],
            }
          : null) ||
        (parsed.last_manager_touch_snapshot && typeof parsed.last_manager_touch_snapshot === "object"
          ? {
              recorded_at: asText(parsed.last_manager_touch_snapshot.recorded_at),
              session_count: asNumber(parsed.last_manager_touch_snapshot.session_count, 0),
              recommendation_label: asText(parsed.last_manager_touch_snapshot.recommendation_label),
              deferred_state: normalizeDeferredStateSnapshot(
                parsed.last_manager_touch_snapshot.deferred_state,
                asText(parsed.last_manager_touch_snapshot.recorded_at),
              ),
              sessions: Array.isArray(parsed.last_manager_touch_snapshot.sessions)
                ? parsed.last_manager_touch_snapshot.sessions.map((entry) => ({
                    ...snapshotEntryFromCard(entry),
                  }))
                : [],
            }
          : null),
      last_manager_touch_at: asText(parsed.last_manager_touch_at || parsed.last_manager_check_at),
      last_manager_touch_snapshot:
        (parsed.last_manager_touch_snapshot && typeof parsed.last_manager_touch_snapshot === "object"
          ? {
              recorded_at: asText(parsed.last_manager_touch_snapshot.recorded_at),
              session_count: asNumber(parsed.last_manager_touch_snapshot.session_count, 0),
              recommendation_label: asText(parsed.last_manager_touch_snapshot.recommendation_label),
              deferred_state: normalizeDeferredStateSnapshot(
                parsed.last_manager_touch_snapshot.deferred_state,
                asText(parsed.last_manager_touch_snapshot.recorded_at),
              ),
              sessions: Array.isArray(parsed.last_manager_touch_snapshot.sessions)
                ? parsed.last_manager_touch_snapshot.sessions.map((entry) => ({
                    ...snapshotEntryFromCard(entry),
                  }))
                : [],
            }
          : null) ||
        (parsed.last_manager_check_snapshot && typeof parsed.last_manager_check_snapshot === "object"
          ? {
              recorded_at: asText(parsed.last_manager_check_snapshot.recorded_at),
              session_count: asNumber(parsed.last_manager_check_snapshot.session_count, 0),
              recommendation_label: asText(parsed.last_manager_check_snapshot.recommendation_label),
              deferred_state: normalizeDeferredStateSnapshot(
                parsed.last_manager_check_snapshot.deferred_state,
                asText(parsed.last_manager_check_snapshot.recorded_at),
              ),
              sessions: Array.isArray(parsed.last_manager_check_snapshot.sessions)
                ? parsed.last_manager_check_snapshot.sessions.map((entry) => ({
                    ...snapshotEntryFromCard(entry),
                }))
                : [],
            }
          : null),
      last_deferred_response_anchor: normalizeDeferredStateSnapshot(
        parsed.last_deferred_response_anchor,
        asText(parsed.last_manager_check_at || parsed.last_manager_touch_at),
      ),
      manager_items: managerItemMemoryFromRaw(parsed.manager_items),
      manager_item_events: trimManagerItemEvents(parsed.manager_item_events),
    };
  } catch {
    return createEmptyPortfolioDigestMemory();
  }
}

export function serializePortfolioDigestMemory(memory) {
  return JSON.stringify(loadPortfolioDigestMemory(memory));
}

export function buildPortfolioDigestSnapshot(cards = [], recommendation = null, options = {}) {
  const recordedAt = asText(options.recordedAt || options.nowIso || new Date().toISOString());
  const normalizedCards = (Array.isArray(cards) ? cards : []).filter(Boolean).map(snapshotEntryFromCard);
  return {
    recorded_at: recordedAt,
    session_count: normalizedCards.length,
    recommendation_label: asText(recommendation?.label),
    deferred_state: normalizeDeferredStateSnapshot(options.deferredState, recordedAt),
    sessions: normalizedCards,
  };
}

export function recordPortfolioDigestTouch(memory, snapshot, options = {}) {
  const currentMemory = loadPortfolioDigestMemory(memory);
  const nextSnapshot =
    snapshot && typeof snapshot === "object"
      ? buildPortfolioDigestSnapshot(
          snapshot.sessions || [],
          { label: snapshot.recommendation_label },
          {
            recordedAt: asText(snapshot.recorded_at || options.recordedAt || new Date().toISOString()),
            deferredState: snapshot.deferred_state,
          },
        )
      : buildPortfolioDigestSnapshot([], null, {
          recordedAt: asText(options.recordedAt || new Date().toISOString()),
        });
  const nextSnapshotMap = buildSnapshotMap(nextSnapshot);
  const previousAnchorMs = parseDateMs(
    currentMemory.last_manager_check_at || currentMemory.last_manager_touch_at,
  );
  const nextManagerItems = Object.fromEntries(
    Object.entries(currentMemory.manager_items || {}).map(([sessionId, entry]) => {
      const normalized = normalizeManagerItemMemoryEntry(sessionId, entry);
      if (!normalized) {
        return null;
      }
      if (
        isManagerItemDeferred(normalized) &&
        asText(normalized.defer_basis_key) === MANAGER_SNOOZE_NEXT_CHECK_KEY &&
        parseDateMs(nextSnapshot.recorded_at) > parseDateMs(normalized.deferred_at)
      ) {
        return [
          normalized.session_id,
          {
            ...normalized,
            active: false,
            reopened_at: nextSnapshot.recorded_at,
            return_reason: MANAGER_RETURN_REASON_NEXT_CHECK,
          },
        ];
      }
      return [normalized.session_id, normalized];
    }).filter(Boolean),
  );
  const returnedEvents = Object.values(nextManagerItems)
    .filter((entry) => asText(entry?.return_reason) === MANAGER_RETURN_REASON_NEXT_CHECK)
    .filter((entry) => asText(entry?.reopened_at) === nextSnapshot.recorded_at)
    .map((entry) => ({
      session_id: asText(entry?.session_id),
      session_handle: asText(entry?.session_handle || entry?.session_id, "session"),
      event_type: "returned_from_snooze",
      return_reason: MANAGER_RETURN_REASON_NEXT_CHECK,
      at: nextSnapshot.recorded_at,
      basis_key: MANAGER_SNOOZE_NEXT_CHECK_KEY,
      basis_label: MANAGER_SNOOZE_NEXT_CHECK_LABEL,
      next_action_label: asText(entry?.next_action_label),
      current_blocker: asText(entry?.current_blocker),
    }));
  const overdueEvents = Object.values(nextManagerItems)
    .filter((entry) => !Boolean(entry?.active))
    .filter((entry) => parseDateMs(entry?.reopened_at) > 0)
    .filter((entry) => parseDateMs(entry?.reopened_at) < parseDateMs(nextSnapshot.recorded_at))
    .filter((entry) => {
      const reopenedAtMs = parseDateMs(entry?.reopened_at);
      return previousAnchorMs ? reopenedAtMs >= previousAnchorMs : false;
    })
    .filter((entry) => isActionableSnapshotEntry(nextSnapshotMap.get(asText(entry?.session_id))))
    .map((entry) => ({
      session_id: asText(entry?.session_id),
      session_handle: asText(entry?.session_handle || entry?.session_id, "session"),
      event_type: "overdue_after_return",
      return_reason: asText(entry?.return_reason),
      at: nextSnapshot.recorded_at,
      basis_key: asText(entry?.defer_basis_key),
      basis_label: asText(entry?.defer_basis_label),
      next_action_label: asText(entry?.next_action_label),
      current_blocker: asText(entry?.current_blocker),
    }));
  return {
    schema_version: 4,
    last_manager_check_at: nextSnapshot.recorded_at,
    last_manager_check_snapshot: nextSnapshot,
    last_manager_touch_at: nextSnapshot.recorded_at,
    last_manager_touch_snapshot: nextSnapshot,
    last_deferred_response_anchor: null,
    manager_items: nextManagerItems,
    manager_item_events: trimManagerItemEvents([
      ...overdueEvents,
      ...returnedEvents,
      ...(currentMemory.manager_item_events || []),
    ]),
    previous_last_manager_check_at:
      currentMemory.last_manager_check_at || currentMemory.last_manager_touch_at,
    previous_last_manager_touch_at: currentMemory.last_manager_touch_at,
  };
}

export function recordDeferredResponseAnchor(memory, digest, options = {}) {
  const currentMemory = loadPortfolioDigestMemory(memory);
  return {
    ...currentMemory,
    schema_version: 4,
    last_deferred_response_anchor: buildDeferredResponseAnchorState(digest, {
      recordedAt: asText(options.recordedAt || new Date().toISOString()),
      source: asText(options.source || "shell_action"),
      targetSessionId: asText(options.targetSessionId),
      actionLabel: asText(options.actionLabel),
    }),
  };
}

export function deferPortfolioManagerItem(memory, card, options = {}) {
  const currentMemory = loadPortfolioDigestMemory(memory);
  const deferredAt = asText(options.deferredAt || new Date().toISOString());
  const deferBasisKey = asText(options.deferBasisKey || MANAGER_SNOOZE_NEXT_CHECK_KEY);
  const deferBasisLabel = asText(
    options.deferBasisLabel ||
      (deferBasisKey === MANAGER_SNOOZE_UNTIL_REOPEN_KEY
        ? MANAGER_SNOOZE_UNTIL_REOPEN_LABEL
        : MANAGER_SNOOZE_NEXT_CHECK_LABEL),
  );
  const deferredEntry = buildDeferredManagerItemEntry(card, {
    deferredAt,
    deferBasisKey,
    deferBasisLabel,
  });
  if (!deferredEntry?.session_id) {
    return {
      memory: currentMemory,
      changed: false,
      blocked_reason: "This manager item cannot be snoozed because its session identity is missing.",
      notice: "",
    };
  }
  return {
    memory: {
      ...currentMemory,
      manager_items: {
        ...(currentMemory.manager_items || {}),
        [deferredEntry.session_id]: deferredEntry,
      },
      manager_item_events: trimManagerItemEvents([
        {
          session_id: deferredEntry.session_id,
          session_handle: deferredEntry.session_handle,
          event_type: "deferred",
          at: deferredAt,
          basis_key: deferBasisKey,
          basis_label: deferBasisLabel,
          next_action_label: deferredEntry.next_action_label,
          current_blocker: deferredEntry.current_blocker,
        },
        ...(currentMemory.manager_item_events || []),
      ]),
    },
    changed: true,
    blocked_reason: "",
    notice:
      deferBasisKey === MANAGER_SNOOZE_UNTIL_REOPEN_KEY
        ? `${deferredEntry.session_handle} is deferred until you reopen it explicitly. Backend blocking truth is unchanged and the item remains visible in the shell queue.`
        : `${deferredEntry.session_handle} is snoozed until the next manager check. Backend blocking truth is unchanged and the item remains visible in the shell queue.`,
  };
}

export function reopenPortfolioManagerItem(memory, card, options = {}) {
  const currentMemory = loadPortfolioDigestMemory(memory);
  const sessionId = asText(card?.session_id);
  const existing = normalizeManagerItemMemoryEntry(sessionId, currentMemory.manager_items?.[sessionId]);
  if (!sessionId || !existing || !isManagerItemDeferred(existing)) {
    return {
      memory: currentMemory,
      changed: false,
      blocked_reason: "This manager item is not currently snoozed.",
      notice: "",
    };
  }
  const reopenedAt = asText(options.reopenedAt || new Date().toISOString());
  return {
    memory: {
      ...currentMemory,
      manager_items: {
        ...(currentMemory.manager_items || {}),
        [sessionId]: {
          ...existing,
          active: false,
          reopened_at: reopenedAt,
          return_reason: MANAGER_RETURN_REASON_MANUAL_REOPEN,
        },
      },
      manager_item_events: trimManagerItemEvents([
        {
          session_id: existing.session_id,
          session_handle: existing.session_handle,
          event_type: "reopened_manual",
          at: reopenedAt,
          basis_key: existing.defer_basis_key,
          basis_label: existing.defer_basis_label,
          next_action_label: existing.next_action_label,
          current_blocker: existing.current_blocker,
          return_reason: MANAGER_RETURN_REASON_MANUAL_REOPEN,
        },
        ...(currentMemory.manager_item_events || []),
      ]),
    },
    changed: true,
    blocked_reason: "",
    notice: `${existing.session_handle} returned to the active agenda. Backend truth and session lineage are unchanged.`,
  };
}

function isActionableOperatorQueueGroup(groupKey) {
  return (
    groupKey === "pending_review_intervention" ||
    groupKey === "stale_escalated" ||
    groupKey === "blocking_now" ||
    groupKey === "resumable"
  );
}

function isActionableSnapshotEntry(entry) {
  if (!entry) {
    return false;
  }
  const groupKey = asText(entry.operator_queue_group);
  if (groupKey) {
    return isActionableOperatorQueueGroup(groupKey);
  }
  const queueBucket = asText(entry.queue_bucket);
  return (
    queueBucket === "new_blocking_now" ||
    queueBucket === "stale_escalated_blocking" ||
    queueBucket === "seen_unresolved_blocking" ||
    queueBucket === "acknowledged_unresolved_blocking" ||
    queueBucket === "resumable"
  );
}

function sameAgendaItemStillActive(card, previousEntry) {
  if (!card || !previousEntry || !isActionableSnapshotEntry(previousEntry)) {
    return false;
  }
  const checkpointDelta =
    asNumber(card?.checkpoint_count, 0) - asNumber(previousEntry?.checkpoint_count, 0);
  const cycleDelta = asNumber(card?.current_cycle, 0) - asNumber(previousEntry?.current_cycle, 0);
  const summarySignatureChanged =
    asText(card?.summary_signature) &&
    asText(previousEntry?.summary_signature) &&
    asText(card?.summary_signature) !== asText(previousEntry?.summary_signature);
  const blockerChanged =
    asText(card?.current_blocker) !== asText(previousEntry?.current_blocker);
  const actionChanged = operatorActionLabel(card) !== operatorActionLabel(previousEntry);
  const queueBucketChanged = asText(card?.queue_bucket) !== asText(previousEntry?.queue_bucket);
  return !(
    checkpointDelta > 0 ||
    cycleDelta > 0 ||
    summarySignatureChanged ||
    blockerChanged ||
    actionChanged ||
    queueBucketChanged
  );
}

function agendaStateForCard(card, previousEntry, managerItemEntry, anchorRecordedAt) {
  if (deferBasisStillActive(managerItemEntry, anchorRecordedAt)) {
    if (asText(managerItemEntry?.defer_basis_key) === MANAGER_SNOOZE_UNTIL_REOPEN_KEY) {
      return {
        key: "deferred_until_reopen",
        label: "Deferred until reopened",
        detail:
          "This manager item is parked out of the active agenda until the operator reopens it explicitly. Backend blocking truth is unchanged, and the item remains visible in the deferred queue.",
      };
    }
    return {
      key: "deferred_until_next_manager_check",
      label: "Deferred until next manager check",
      detail:
        "This manager item was snoozed locally. Backend blocking truth is unchanged, and the item remains visible in the broader shell queue until the next manager check or explicit reopen.",
    };
  }
  const reopenedAtMs = parseDateMs(managerItemEntry?.reopened_at);
  const anchorMs = parseDateMs(anchorRecordedAt);
  const returnedSinceAnchor = reopenedAtMs && (!anchorMs || reopenedAtMs >= anchorMs);
  const returnedBeforeAnchor = reopenedAtMs && anchorMs && reopenedAtMs < anchorMs;
  const returnReason = asText(managerItemEntry?.return_reason);
  if (returnedBeforeAnchor) {
    return {
      key: "overdue_after_return",
      label: "Overdue after return",
      detail:
        "This item already came back from the deferred queue and remained unresolved through another manager-check boundary, so it now outranks newly due deferred work.",
    };
  }
  if (returnReason === MANAGER_RETURN_REASON_NEXT_CHECK && returnedSinceAnchor) {
    return {
      key: "due_return_now",
      label: "Due now from deferred queue",
      detail: `This item returned because ${asText(
        managerItemEntry?.defer_basis_label,
        "its defer policy",
      )} came due at the latest manager check. Backend truth is unchanged.`,
    };
  }
  if (returnReason === MANAGER_RETURN_REASON_MANUAL_REOPEN && returnedSinceAnchor) {
    return {
      key: "reopened_after_defer",
      label: "Reopened manually",
      detail:
        "This item returned from a prior defer/snooze state because the operator reopened it explicitly. Backend truth and session lineage are unchanged.",
    };
  }
  const currentGroup = classifyOperatorQueueGroup(card);
  if (currentGroup === "stale_escalated") {
    return {
      key: "overdue_manager_item",
      label: "Overdue manager item",
      detail:
        "This operator item stayed unresolved across manager-check boundaries and now needs renewed attention.",
    };
  }
  if (!previousEntry || !isActionableSnapshotEntry(previousEntry)) {
    return {
      key: "new_since_last_check",
      label: "New since last check",
      detail:
        "This operator item was not present as actionable at the last manager check and needs first review now.",
    };
  }
  if (!sameAgendaItemStillActive(card, previousEntry)) {
    return {
      key: "new_since_last_check",
      label: "New since last check",
      detail:
        "This session advanced enough after the last manager check to replace the prior agenda item with a fresh manager task.",
    };
  }
  return {
    key: "reviewed_still_pending",
    label: "Reviewed but still pending",
    detail:
      "This item was already visible at the last manager check and still needs operator action.",
  };
}

function agendaSummaryLine(item) {
  return `${asText(item?.session_handle || item?.session_id, "session")} · ${asText(
    item?.next_action_label,
    "Open session",
  )}`;
}

function completionOutcomeForCard(card) {
  if (!card) {
    return {
      label: "Completed since last manager check",
      detail:
        "The previously actionable manager item no longer appears in the current shell queue.",
      state_label: "No longer visible in the current shell queue",
    };
  }
  const groupKey = classifyOperatorQueueGroup(card);
  if (groupKey === "resumable") {
    return {
      label: "Completed; session remains resumable",
      detail:
        "The operator handled the prior agenda item and the same session now sits at an explicit resumable boundary.",
      state_label: "Resumable session",
    };
  }
  if (groupKey === "running_waiting") {
    return {
      label: "Completed; session is progressing inside bounds",
      detail:
        "The operator handled the prior agenda item and the same session moved back into bounded running/waiting work.",
      state_label: "Running / waiting inside bounds",
    };
  }
  if (groupKey === "completed_halted") {
    return {
      label: "Completed; session moved into completed history",
      detail:
        "The operator handled the prior agenda item and the session is now reviewable completed/halted history.",
      state_label: "Completed / halted",
    };
  }
  if (groupKey === "archived_informational") {
    return {
      label: "Completed; session fell back to history",
      detail:
        "The operator handled the prior agenda item and the session no longer competes with current actionable queue work.",
      state_label: "Archived / informational",
    };
  }
  return {
    label: "Completed since last manager check",
    detail:
      "The prior agenda item no longer leads the current shell queue, even though the session may still need bounded follow-up later.",
    state_label: asText(card?.operator_queue_label || card?.state_label || card?.lifecycle_state, "Current state changed"),
  };
}

export function buildPortfolioManagerAgenda(cards = [], recommendation = null, memory, options = {}) {
  const currentMemory = loadPortfolioDigestMemory(memory);
  const anchorSnapshot =
    currentMemory.last_manager_check_snapshot || currentMemory.last_manager_touch_snapshot || null;
  const anchorRecordedAt =
    asText(anchorSnapshot?.recorded_at) ||
    asText(currentMemory.last_manager_check_at || currentMemory.last_manager_touch_at);
  const previousSnapshotMap = buildSnapshotMap(anchorSnapshot);
  const currentCardMap = new Map(
    (Array.isArray(cards) ? cards : [])
      .filter((card) => asText(card?.session_id))
      .map((card) => [asText(card.session_id), card]),
  );
  const managerItemMap = currentMemory.manager_items || {};
  const anchorMs = parseDateMs(anchorRecordedAt);
  const managerEventsSinceCheck = (currentMemory.manager_item_events || []).filter((event) => {
    const eventMs = parseDateMs(event?.at);
    if (!eventMs) {
      return false;
    }
    return anchorMs ? eventMs >= anchorMs : true;
  });

  const actionableCandidateCards = (Array.isArray(cards) ? cards : [])
    .filter(Boolean)
    .map((card) => {
      const sessionId = asText(card?.session_id);
      const previousEntry = previousSnapshotMap.get(asText(card?.session_id));
      const managerItemEntry = normalizeManagerItemMemoryEntry(
        sessionId,
        managerItemMap[sessionId],
      );
      const agendaState = agendaStateForCard(
        card,
        previousEntry,
        managerItemEntry,
        anchorRecordedAt,
      );
      return {
        ...card,
        agenda_state_key: agendaState.key,
        agenda_state_label: agendaState.label,
        agenda_state_detail: agendaState.detail,
        manager_deferred_at: asText(managerItemEntry?.deferred_at),
        manager_defer_basis_key: asText(managerItemEntry?.defer_basis_key),
        manager_defer_basis_label: asText(managerItemEntry?.defer_basis_label),
        manager_reopened_at: asText(managerItemEntry?.reopened_at),
        manager_return_reason: asText(managerItemEntry?.return_reason),
        manager_return_reason_label: managerReturnReasonLabel(managerItemEntry),
      };
    })
    .filter((card) => isActionableOperatorQueueGroup(classifyOperatorQueueGroup(card)))
    .sort(sortAgendaCards);

  const deferredItems = actionableCandidateCards
    .filter((card) =>
      ["deferred_until_next_manager_check", "deferred_until_reopen"].includes(
        card.agenda_state_key,
      ),
    )
    .slice(0, DIGEST_LIST_LIMIT);
  const actionableCards = actionableCandidateCards
    .filter((card) =>
      !["deferred_until_next_manager_check", "deferred_until_reopen"].includes(
        card.agenda_state_key,
      ),
    )
    .sort(sortAgendaCards);

  const actionableCurrentSessionIds = new Set(actionableCards.map((card) => asText(card.session_id)));
  const completedItems = Array.from(previousSnapshotMap.values())
    .filter((entry) => isActionableSnapshotEntry(entry))
    .filter((entry) => {
      const currentCard = currentCardMap.get(asText(entry.session_id));
      if (!currentCard) {
        return true;
      }
      if (!isActionableOperatorQueueGroup(classifyOperatorQueueGroup(currentCard))) {
        return true;
      }
      return (
        agendaStateForCard(
          currentCard,
          entry,
          normalizeManagerItemMemoryEntry(
            asText(currentCard?.session_id),
            managerItemMap[asText(currentCard?.session_id)],
          ),
          anchorRecordedAt,
        ).key === "new_since_last_check"
      );
    })
    .map((entry) => {
      const currentCard = currentCardMap.get(asText(entry.session_id));
      const completionOutcome = completionOutcomeForCard(currentCard);
      return {
        session_id: asText(entry.session_id),
        session_handle: asText(entry.session_handle || entry.session_id, "session"),
        next_action_label: asText(entry.next_action_label, "Open session"),
        agenda_state_key: "completed_since_last_manager_check",
        agenda_state_label: "Completed since last manager check",
        agenda_state_detail:
          "This operator item was actionable at the last manager check and no longer leads the current agenda.",
        completion_outcome_label: completionOutcome.label,
        completion_outcome_detail: completionOutcome.detail,
        resulting_state_label: completionOutcome.state_label,
        resulting_queue_bucket: asText(currentCard?.queue_bucket),
        resulting_operator_queue_group: asText(currentCard ? classifyOperatorQueueGroup(currentCard) : ""),
      };
    })
    .slice(0, DIGEST_LIST_LIMIT);

  const newItems = actionableCards.filter((card) => card.agenda_state_key === "new_since_last_check");
  const dueItems = actionableCards.filter((card) => card.agenda_state_key === "due_return_now");
  const reopenedItems = actionableCards.filter((card) => card.agenda_state_key === "reopened_after_defer");
  const reviewedPendingItems = actionableCards.filter(
    (card) => card.agenda_state_key === "reviewed_still_pending",
  );
  const overdueReturnedItems = actionableCards.filter(
    (card) => card.agenda_state_key === "overdue_after_return",
  );
  const overdueItems = actionableCards.filter((card) =>
    ["overdue_manager_item", "overdue_after_return"].includes(card.agenda_state_key),
  );
  const stillPendingFromBeforeCheck =
    reviewedPendingItems.length + overdueItems.length + dueItems.length + reopenedItems.length;

  const currentItem = actionableCards[0] || null;
  const nextItem = actionableCards[1] || null;
  const justCompletedItem = completedItems[0] || null;
  const leadDueItem = dueItems[0] || null;
  const leadReopenedItem = reopenedItems[0] || null;
  const leadOverdueItem = overdueItems[0] || null;
  const leadDeferredItem = deferredItems[0] || null;
  const itemStateBySessionId = actionableCandidateCards.reduce((accumulator, card) => {
    const sessionId = asText(card.session_id);
    if (sessionId) {
      accumulator[sessionId] = {
        key: asText(card.agenda_state_key),
        label: asText(card.agenda_state_label),
        detail: asText(card.agenda_state_detail),
      };
    }
    return accumulator;
  }, {});
  const deferredSinceLastCheck = managerEventsSinceCheck.filter(
    (event) => asText(event?.event_type) === "deferred",
  );
  const dueReturnedSinceLastCheck = managerEventsSinceCheck.filter(
    (event) => asText(event?.event_type) === "returned_from_snooze",
  );
  const reopenedSinceLastCheck = managerEventsSinceCheck.filter(
    (event) => asText(event?.event_type) === "reopened_manual",
  );
  const overdueAfterReturnSinceLastCheck = managerEventsSinceCheck.filter(
    (event) => asText(event?.event_type) === "overdue_after_return",
  );

  const orderingRationale = currentItem
    ? currentItem.agenda_state_key === "overdue_after_return"
      ? "This item already returned from the deferred queue and remained unresolved through another manager check, so it now leads the active agenda."
      : currentItem.agenda_state_key === "due_return_now"
        ? `This item is current now because ${asText(
            currentItem.manager_defer_basis_label,
            "its defer basis",
          )} came due at the latest manager check.`
        : currentItem.agenda_state_key === "reopened_after_defer"
          ? "This item is current now because the operator reopened it manually from the deferred queue."
          : asText(
              recommendation?.detail,
              "The top agenda item is the highest-priority truthful operator task in the current shell queue.",
            )
    : "No blocking or resumable operator task is leading the current shell agenda.";

  const throughput = {
    headline: `${pluralize(completedItems.length, "item")} completed · ${pluralize(
      stillPendingFromBeforeCheck,
      "item",
    )} still pending · ${pluralize(newItems.length, "item")} new · ${pluralize(
      overdueItems.length,
      "item",
    )} overdue · ${pluralize(dueItems.length, "item")} due now · ${pluralize(
      deferredItems.length,
      "item",
    )} deferred`,
    detail: currentItem
      ? `${orderingRationale} ${nextItem ? `Next: ${agendaSummaryLine(nextItem)}.` : "No next agenda item is queued yet."}`
      : justCompletedItem
        ? `${asText(justCompletedItem.session_handle || justCompletedItem.session_id, "session")} moved out of the current agenda slot.`
        : leadDeferredItem
          ? `${asText(
              leadDeferredItem.session_handle || leadDeferredItem.session_id,
              "session",
            )} remains deferred with return basis ${asText(
              leadDeferredItem.manager_defer_basis_label,
              "Deferred",
            )}.`
          : "No blocking or resumable operator task is currently queued.",
    current_item_summary: currentItem ? agendaSummaryLine(currentItem) : "",
    next_item_summary: nextItem ? agendaSummaryLine(nextItem) : "",
    completed_item_summary: justCompletedItem
      ? `${asText(justCompletedItem.session_handle || justCompletedItem.session_id, "session")} · ${asText(
          justCompletedItem.completion_outcome_label,
        )}`
      : "",
    due_item_summary: leadDueItem
      ? `${asText(leadDueItem.session_handle || leadDueItem.session_id, "session")} · ${asText(
          leadDueItem.manager_return_reason_label,
          leadDueItem.agenda_state_label,
        )}`
      : "",
    deferred_item_summary: leadDeferredItem
      ? `${asText(leadDeferredItem.session_handle || leadDeferredItem.session_id, "session")} · ${asText(
          leadDeferredItem.manager_defer_basis_label,
          "Deferred",
        )}`
      : "",
    completed_since_last_check: completedItems.length,
    still_pending_from_before_check: stillPendingFromBeforeCheck,
    new_since_last_check: newItems.length,
    overdue_manager_items: overdueItems.length,
    overdue_after_return: overdueReturnedItems.length,
    due_now: dueItems.length,
    reopened_items: reopenedItems.length,
    deferred_items: deferredItems.length,
    deferred_since_last_check: deferredSinceLastCheck.length,
    due_returned_since_last_check: dueReturnedSinceLastCheck.length,
    returned_from_snooze_since_last_check: dueReturnedSinceLastCheck.length,
    reopened_since_last_check: reopenedSinceLastCheck.length,
    overdue_after_return_since_last_check: overdueAfterReturnSinceLastCheck.length,
    actionable_now: actionableCards.length,
  };

  return {
    anchor: {
      basis_label: "Since last manager check",
      recorded_at: anchorRecordedAt,
      description: anchorRecordedAt
        ? `Comparing the current shell state against the last acknowledged manager digest at ${anchorRecordedAt}.`
        : "No prior manager check is recorded yet. This agenda treats the current actionable shell state as newly reviewed work.",
    },
    checked_at: anchorRecordedAt,
    currentItem,
    nextItem,
    pendingItems: actionableCards.slice(0, DIGEST_LIST_LIMIT),
    newItems: newItems.slice(0, DIGEST_LIST_LIMIT),
    reviewedPendingItems: reviewedPendingItems.slice(0, DIGEST_LIST_LIMIT),
    overdueItems: overdueItems.slice(0, DIGEST_LIST_LIMIT),
    dueItems: dueItems.slice(0, DIGEST_LIST_LIMIT),
    deferredItems,
    reopenedItems: reopenedItems.slice(0, DIGEST_LIST_LIMIT),
    completedItems,
    clearedItems: completedItems,
    justCompletedItem,
    itemStateBySessionId,
    counts: {
      actionable_now: actionableCards.length,
      new_since_last_check: newItems.length,
      reviewed_still_pending: reviewedPendingItems.length,
      overdue_manager_items: overdueItems.length,
      overdue_after_return: overdueReturnedItems.length,
      still_pending_from_before_check: stillPendingFromBeforeCheck,
      completed_since_last_check: completedItems.length,
      cleared_since_last_check: completedItems.length,
      due_now: dueItems.length,
      reopened_items: reopenedItems.length,
      deferred_items: deferredItems.length,
      deferred_since_last_check: deferredSinceLastCheck.length,
      due_returned_since_last_check: dueReturnedSinceLastCheck.length,
      returned_from_snooze_since_last_check: dueReturnedSinceLastCheck.length,
      reopened_since_last_check: reopenedSinceLastCheck.length,
      overdue_after_return_since_last_check: overdueAfterReturnSinceLastCheck.length,
    },
    currentAgendaSummary: currentItem
      ? `${agendaSummaryLine(currentItem)} · ${asText(currentItem.agenda_state_label)}`
      : "No pending operator agenda item remains right now.",
    nextAgendaSummary: nextItem
      ? `${agendaSummaryLine(nextItem)} · ${asText(nextItem.agenda_state_label)}`
      : "No next agenda item is queued after the current top item.",
    completedAgendaSummary: justCompletedItem
      ? `${asText(justCompletedItem.session_handle || justCompletedItem.session_id, "session")} · ${asText(
          justCompletedItem.completion_outcome_label,
          "Completed since last manager check",
        )}`
      : "No agenda item has been completed since the last manager check yet.",
    overdueAgendaSummary: leadOverdueItem
      ? `${agendaSummaryLine(leadOverdueItem)} · ${asText(leadOverdueItem.agenda_state_label)}`
      : "No overdue manager item is currently queued.",
    dueAgendaSummary: leadDueItem
      ? `${agendaSummaryLine(leadDueItem)} · ${asText(leadDueItem.agenda_state_label)}`
      : "No deferred item is due to return right now.",
    deferredAgendaSummary: leadDeferredItem
      ? `${agendaSummaryLine(leadDeferredItem)} · ${asText(
          leadDeferredItem.manager_defer_basis_label,
          "Deferred",
        )}`
      : "No deferred manager item is currently parked out of the active agenda.",
    reopenedAgendaSummary: leadReopenedItem
      ? `${agendaSummaryLine(leadReopenedItem)} · ${asText(
          leadReopenedItem.agenda_state_label,
          "Reopened manually",
        )}`
      : "No deferred item has been reopened manually since the current manager check.",
    throughput,
    rationale: orderingRationale,
  };
}

export function classifyOperatorQueueGroup(card) {
  if (Boolean(card?.archived)) {
    return "archived_informational";
  }
  const queueBucket = asText(card?.queue_bucket, "clear");
  if (queueBucket === "stale_escalated_blocking") {
    return "stale_escalated";
  }
  if (hasBlockingBucket(card)) {
    return isReviewInterventionCard(card) ? "pending_review_intervention" : "blocking_now";
  }
  if (queueBucket === "resumable") {
    return "resumable";
  }
  if (queueBucket === "running_waiting") {
    return "running_waiting";
  }
  if (queueBucket === "completed_halted") {
    return "completed_halted";
  }
  return "archived_informational";
}

export function buildPortfolioOperatorQueue(cards = [], recommendation = null) {
  const normalizedCards = (Array.isArray(cards) ? cards : [])
    .filter(Boolean)
    .map((card) => {
      const groupKey = classifyOperatorQueueGroup(card);
      const groupDefinition =
        PORTFOLIO_OPERATOR_QUEUE_GROUPS.find((item) => item.key === groupKey) ||
        PORTFOLIO_OPERATOR_QUEUE_GROUPS[PORTFOLIO_OPERATOR_QUEUE_GROUPS.length - 1];
      return {
        ...card,
        operator_queue_group: groupKey,
        operator_queue_label: groupDefinition.label,
        operator_queue_detail: groupDefinition.detail,
        operator_queue_tone: groupDefinition.tone,
      };
    })
    .sort(sortCards);

  const sections = PORTFOLIO_OPERATOR_QUEUE_GROUPS.map((group) => {
    const sectionCards = normalizedCards.filter((card) => card.operator_queue_group === group.key);
    return {
      ...group,
      cards: sectionCards,
      count: sectionCards.length,
    };
  }).filter((section) => section.count > 0);

  const groupedCounts = PORTFOLIO_OPERATOR_QUEUE_GROUPS.map((group) => ({
    key: group.key,
    label: group.label,
    tone: group.tone,
    count: sections.find((section) => section.key === group.key)?.count || 0,
  })).filter((item) => item.count > 0);

  const actionableNowCount = sections
    .filter((section) =>
      ["pending_review_intervention", "stale_escalated", "blocking_now", "resumable"].includes(
        section.key,
      ),
    )
    .reduce((total, section) => total + section.count, 0);
  const safeToIgnoreCount = sections
    .filter((section) =>
      ["running_waiting", "completed_halted", "archived_informational"].includes(section.key),
    )
    .reduce((total, section) => total + section.count, 0);

  return {
    sections,
    groupedCounts,
    counts: {
      actionable_now: actionableNowCount,
      safe_to_ignore: safeToIgnoreCount,
      review_intervention: groupedCounts.find((item) => item.key === "pending_review_intervention")?.count || 0,
      stale_escalated: groupedCounts.find((item) => item.key === "stale_escalated")?.count || 0,
      resumable: groupedCounts.find((item) => item.key === "resumable")?.count || 0,
      running_waiting: groupedCounts.find((item) => item.key === "running_waiting")?.count || 0,
      completed_halted: groupedCounts.find((item) => item.key === "completed_halted")?.count || 0,
      archived_informational:
        groupedCounts.find((item) => item.key === "archived_informational")?.count || 0,
    },
    dominantAction: recommendation
      ? {
          label: asText(recommendation.label, "Review portfolio queue"),
          detail: asText(
            recommendation.detail,
            "Open the current operator queue leader before lower-priority portfolio work.",
          ),
          targetSessionId: asText(recommendation.targetSessionId),
          targetCardKey: asText(recommendation.targetCardKey),
        }
      : null,
    shortlist: recommendationShortlist(recommendation),
  };
}

export function buildPortfolioManagerDigest(cards = [], recommendation = null, memory, options = {}) {
  const currentMemory = loadPortfolioDigestMemory(memory);
  const agenda = buildPortfolioManagerAgenda(cards, recommendation, currentMemory, options);
  const currentSnapshot = buildPortfolioDigestSnapshot(cards, recommendation, {
    nowIso: asText(options.nowIso || new Date().toISOString()),
  });
  const previousSnapshot =
    currentMemory.last_manager_check_snapshot || currentMemory.last_manager_touch_snapshot;
  const previousMap = buildSnapshotMap(previousSnapshot);
  const anchorMs = parseDateMs(previousSnapshot?.recorded_at);
  const normalizedCards = (Array.isArray(cards) ? cards : []).filter(Boolean).map((card) => ({
    ...card,
    operator_queue_group: classifyOperatorQueueGroup(card),
  }));

  const advancedSessions = [];
  const newBlockingSessions = [];
  const newlyResumableSessions = [];
  const completedSinceTouchSessions = [];
  const resolvedBlockerSessions = [];
  let totalCheckpointDelta = 0;

  for (const card of normalizedCards) {
    const previous = previousMap.get(asText(card.session_id));
    const checkpointDelta = Math.max(
      0,
      asNumber(card.checkpoint_count, 0) - asNumber(previous?.checkpoint_count, 0),
    );
    const cycleDelta = Math.max(
      0,
      asNumber(card.current_cycle, 0) - asNumber(previous?.current_cycle, 0),
    );
    const previousBlocking = hasBlockingBucket(previous);
    const currentBlocking = hasBlockingBucket(card);
    const summaryChanged =
      asText(card.summary_signature) &&
      asText(previous?.summary_signature) &&
      asText(card.summary_signature) !== asText(previous?.summary_signature);

    if (previous && (checkpointDelta > 0 || cycleDelta > 0)) {
      totalCheckpointDelta += checkpointDelta;
      advancedSessions.push({
        ...card,
        checkpoint_delta: checkpointDelta,
        cycle_delta: cycleDelta,
        digest_summary: safeProgressMarker(card),
      });
    }

    if (currentBlocking && (!previousBlocking || summaryChanged)) {
      newBlockingSessions.push({
        ...card,
        digest_summary: asText(card.current_blocker, safeProgressMarker(card)),
      });
    }

    if (asText(card.queue_bucket) === "resumable" && asText(previous?.queue_bucket) !== "resumable") {
      newlyResumableSessions.push({
        ...card,
        digest_summary: safeProgressMarker(card),
      });
    }

    if (
      asText(card.queue_bucket) === "completed_halted" &&
      asText(previous?.queue_bucket) !== "completed_halted"
    ) {
      completedSinceTouchSessions.push({
        ...card,
        digest_summary: safeProgressMarker(card),
      });
    }

    if (!currentBlocking && previousBlocking) {
      resolvedBlockerSessions.push({
        ...card,
        digest_summary: safeProgressMarker(card),
      });
    }
  }

  const topBlockers = normalizedCards
    .filter((card) =>
      ["pending_review_intervention", "stale_escalated", "blocking_now"].includes(
        card.operator_queue_group,
      ),
    )
    .sort(sortCards)
    .slice(0, DIGEST_LIST_LIMIT);
  const pendingOperatorItems = normalizedCards
    .filter((card) =>
      ["pending_review_intervention", "stale_escalated", "blocking_now", "resumable"].includes(
        card.operator_queue_group,
      ),
    )
    .sort(sortCards)
    .slice(0, DIGEST_LIST_LIMIT);
  const progressingWithoutOperator = normalizedCards
    .filter((card) => card.operator_queue_group === "running_waiting")
    .sort(sortCards)
    .slice(0, DIGEST_LIST_LIMIT);

  const pendingOperatorItemCount = normalizedCards.filter((card) =>
    ["pending_review_intervention", "stale_escalated", "blocking_now", "resumable"].includes(
      card.operator_queue_group,
    ),
  ).length;
  const safeToIgnoreCount = normalizedCards.filter((card) =>
    ["running_waiting", "completed_halted", "archived_informational"].includes(
      card.operator_queue_group,
    ),
  ).length;
  const completedManagerItems = Array.isArray(agenda?.completedItems) ? agenda.completedItems : [];
  const stillPendingFromBeforeCheck = asNumber(
    agenda?.counts?.still_pending_from_before_check,
    0,
  );
  const overdueManagerItemCount = asNumber(agenda?.counts?.overdue_manager_items, 0);
  const overdueAfterReturnCount = asNumber(agenda?.counts?.overdue_after_return, 0);
  const dueNowCount = asNumber(agenda?.counts?.due_now, 0);
  const reopenedItemCount = asNumber(agenda?.counts?.reopened_items, 0);
  const deferredManagerItemCount = asNumber(agenda?.counts?.deferred_items, 0);
  const deferredSinceLastCheck = asNumber(agenda?.counts?.deferred_since_last_check, 0);
  const dueReturnedSinceLastCheck = asNumber(
    agenda?.counts?.due_returned_since_last_check,
    asNumber(agenda?.counts?.returned_from_snooze_since_last_check, 0),
  );
  const reopenedSinceLastCheck = asNumber(
    agenda?.counts?.reopened_since_last_check,
    0,
  );
  const overdueAfterReturnSinceLastCheck = asNumber(
    agenda?.counts?.overdue_after_return_since_last_check,
    0,
  );

  const hasComparison = Boolean(previousSnapshot?.recorded_at);
  const headline = hasComparison
    ? [
        `Since the last manager check, ${pluralize(advancedSessions.length, "session")} advanced`,
        `${pluralize(newBlockingSessions.length, "session")} newly blocked`,
        `${pluralize(newlyResumableSessions.length, "session")} became resumable`,
      ].join(" · ")
    : "Manager digest anchor is ready. Future shell returns will summarize cross-session changes from this manager check.";
  const detail = hasComparison
    ? `Pending operator items now: ${pendingOperatorItemCount}. Completed manager items since last check: ${completedManagerItems.length}. Deferred manager items now: ${deferredManagerItemCount}. Due returned items since last check: ${dueReturnedSinceLastCheck}. Reopened manually since last check: ${reopenedSinceLastCheck}. Overdue-after-return items since last check: ${overdueAfterReturnSinceLastCheck}. Still pending from before the last check: ${stillPendingFromBeforeCheck}. Sessions safe to ignore for the moment: ${safeToIgnoreCount}.`
    : "No prior manager check is stored yet in this browser, so the digest is showing the current bounded state as the comparison baseline.";

  const progressLines = advancedSessions
    .slice(0, DIGEST_LIST_LIMIT)
    .map((card) =>
      digestLine(
        card,
        `${card.checkpoint_delta} checkpoint(s), ${card.cycle_delta} cycle(s) · ${safeProgressMarker(card)}`,
      ),
    );
  const blockerLines = topBlockers.map((card) =>
    digestLine(card, asText(card.current_blocker, safeProgressMarker(card))),
  );

  return {
    anchor: {
      basis_key: "since_last_manager_check",
      basis_label: "Since last manager check",
      recorded_at: asText(previousSnapshot?.recorded_at),
      detail: hasComparison
        ? `Comparing the current shell state against the last recorded manager check at ${asText(
            previousSnapshot?.recorded_at,
            "n/a",
          )}.`
        : "No prior manager check was stored for this browser yet. Marking this digest checked will establish the next comparison anchor.",
      has_comparison: hasComparison,
    },
    headline,
    detail,
    currentSnapshot,
    counts: {
      sessions_advanced: advancedSessions.length,
      checkpoint_delta: totalCheckpointDelta,
      new_blockers: newBlockingSessions.length,
      resolved_blockers: resolvedBlockerSessions.length,
      completed_manager_items: completedManagerItems.length,
      due_now: dueNowCount,
      reopened_items: reopenedItemCount,
      deferred_manager_items: deferredManagerItemCount,
      deferred_since_last_check: deferredSinceLastCheck,
      due_returned_since_last_check: dueReturnedSinceLastCheck,
      returned_from_snooze_since_last_check: dueReturnedSinceLastCheck,
      reopened_since_last_check: reopenedSinceLastCheck,
      overdue_after_return_since_last_check: overdueAfterReturnSinceLastCheck,
      still_pending_from_before_check: stillPendingFromBeforeCheck,
      overdue_manager_items: overdueManagerItemCount,
      overdue_after_return: overdueAfterReturnCount,
      resumable_since_touch: newlyResumableSessions.length,
      completed_or_halted_since_touch: completedSinceTouchSessions.length,
      pending_operator_items: pendingOperatorItemCount,
      progressing_without_operator: progressingWithoutOperator.length,
      safe_to_ignore: safeToIgnoreCount,
    },
    counters: [
      {
        key: "sessions_advanced",
        label: "Sessions advanced",
        count: advancedSessions.length,
        detail:
          advancedSessions.length > 0
            ? progressLines.join(" | ")
            : "No session advanced beyond the current digest anchor.",
      },
      {
        key: "checkpoint_delta",
        label: "Checkpoint delta",
        count: totalCheckpointDelta,
        detail:
          totalCheckpointDelta > 0
            ? `${totalCheckpointDelta} checkpoint(s) were added across visible portfolio sessions.`
            : "No additional checkpoints were recorded across the visible portfolio.",
      },
      {
        key: "new_blockers",
        label: "New blockers",
        count: newBlockingSessions.length,
        detail:
          newBlockingSessions.length > 0
            ? newBlockingSessions
                .slice(0, DIGEST_LIST_LIMIT)
                .map((card) => digestLine(card, asText(card.current_blocker, card.next_action_label)))
                .join(" | ")
            : "No newly blocked session appeared since the digest anchor.",
      },
      {
        key: "resolved_blockers",
        label: "Resolved blockers",
        count: resolvedBlockerSessions.length,
        detail:
          resolvedBlockerSessions.length > 0
            ? resolvedBlockerSessions
                .slice(0, DIGEST_LIST_LIMIT)
                .map((card) => digestLine(card, safeProgressMarker(card)))
                .join(" | ")
            : "No previously blocking session cleared beyond the digest anchor.",
      },
      {
        key: "completed_manager_items",
        label: "Completed manager items",
        count: completedManagerItems.length,
        detail:
          completedManagerItems.length > 0
            ? completedManagerItems
                .slice(0, DIGEST_LIST_LIMIT)
                .map((item) =>
                  `${asText(item.session_handle || item.session_id, "session")}: ${asText(
                    item.completion_outcome_label,
                    item.agenda_state_label,
                  )}`,
                )
                .join(" | ")
            : "No previously pending manager item cleared beyond the digest anchor.",
      },
      {
        key: "deferred_since_last_check",
        label: "Deferred since last check",
        count: deferredSinceLastCheck,
        detail:
          deferredSinceLastCheck > 0
            ? (currentMemory.manager_item_events || [])
                .filter((event) => asText(event?.event_type) === "deferred")
                .filter((event) => {
                  const eventMs = parseDateMs(event?.at);
                  return anchorMs ? eventMs >= anchorMs : true;
                })
                .slice(0, DIGEST_LIST_LIMIT)
                .map((event) =>
                  digestLine(
                    event,
                    `${asText(event.basis_label, "Deferred")} · ${asText(
                      event.current_blocker,
                      event.next_action_label,
                    )}`,
                  ),
                )
                .join(" | ")
            : "No manager item was deferred after the current digest anchor.",
      },
      {
        key: "due_returned_since_last_check",
        label: "Due to return",
        count: dueReturnedSinceLastCheck,
        detail:
          dueReturnedSinceLastCheck > 0
            ? (currentMemory.manager_item_events || [])
                .filter((event) => asText(event?.event_type) === "returned_from_snooze")
                .filter((event) => {
                  const eventMs = parseDateMs(event?.at);
                  return anchorMs ? eventMs >= anchorMs : true;
                })
                .slice(0, DIGEST_LIST_LIMIT)
                .map((event) =>
                  digestLine(
                    event,
                    `${asText(event.basis_label, "Returned from snooze")} · ${asText(
                      event.current_blocker,
                      event.next_action_label,
                    )}`,
                  ),
                )
                .join(" | ")
            : "No deferred manager item returned to the active agenda after the digest anchor.",
      },
      {
        key: "reopened_since_last_check",
        label: "Reopened manually",
        count: reopenedSinceLastCheck,
        detail:
          reopenedSinceLastCheck > 0
            ? (currentMemory.manager_item_events || [])
                .filter((event) => asText(event?.event_type) === "reopened_manual")
                .filter((event) => {
                  const eventMs = parseDateMs(event?.at);
                  return anchorMs ? eventMs >= anchorMs : true;
                })
                .slice(0, DIGEST_LIST_LIMIT)
                .map((event) =>
                  digestLine(
                    event,
                    `${asText(event.basis_label, "Reopened manually")} · ${asText(
                      event.current_blocker,
                      event.next_action_label,
                    )}`,
                  ),
                )
                .join(" | ")
            : "No deferred manager item was reopened manually after the digest anchor.",
      },
      {
        key: "overdue_after_return_since_last_check",
        label: "Overdue after return",
        count: overdueAfterReturnSinceLastCheck,
        detail:
          overdueAfterReturnSinceLastCheck > 0
            ? (currentMemory.manager_item_events || [])
                .filter((event) => asText(event?.event_type) === "overdue_after_return")
                .filter((event) => {
                  const eventMs = parseDateMs(event?.at);
                  return anchorMs ? eventMs >= anchorMs : true;
                })
                .slice(0, DIGEST_LIST_LIMIT)
                .map((event) =>
                  digestLine(
                    event,
                    `${asText(event.basis_label, "Returned item")} remained unresolved and crossed into overdue-after-return.`,
                  ),
                )
                .join(" | ")
            : "No returned deferred item crossed into overdue-after-return after the digest anchor.",
      },
      {
        key: "still_pending_from_before_check",
        label: "Still pending from before last check",
        count: stillPendingFromBeforeCheck,
        detail:
          stillPendingFromBeforeCheck > 0
            ? [...(agenda?.overdueItems || []), ...(agenda?.reviewedPendingItems || [])]
                .slice(0, DIGEST_LIST_LIMIT)
                .map((card) =>
                  digestLine(card, asText(card.agenda_state_label, asText(card.current_blocker, card.next_action_label))),
                )
                .join(" | ")
            : "No previously reviewed manager item is still pending.",
      },
      {
        key: "overdue_manager_items",
        label: "Overdue manager items",
        count: overdueManagerItemCount,
        detail:
          overdueManagerItemCount > 0
            ? (agenda?.overdueItems || [])
                .slice(0, DIGEST_LIST_LIMIT)
                .map((card) => digestLine(card, asText(card.current_blocker, card.next_action_label)))
                .join(" | ")
            : "No overdue manager item is currently queued.",
      },
      {
        key: "completed_or_halted_since_touch",
        label: "Completed / halted",
        count: completedSinceTouchSessions.length,
        detail:
          completedSinceTouchSessions.length > 0
            ? completedSinceTouchSessions
                .slice(0, DIGEST_LIST_LIMIT)
                .map((card) => digestLine(card, safeProgressMarker(card)))
                .join(" | ")
            : "No additional session moved into completed/halted history since the anchor.",
      },
      {
        key: "resumable_since_touch",
        label: "Resumable now",
        count: newlyResumableSessions.length,
        detail:
          newlyResumableSessions.length > 0
            ? newlyResumableSessions
                .slice(0, DIGEST_LIST_LIMIT)
                .map((card) => digestLine(card, safeProgressMarker(card)))
                .join(" | ")
            : "No additional session became resumable since the digest anchor.",
      },
    ],
    topBlockers,
    pendingOperatorItems,
    progressingWithoutOperator,
    advancedSessions,
    newBlockingSessions,
    newlyResumableSessions,
    completedSinceTouchSessions,
    resolvedBlockerSessions,
    completedManagerItems,
    dueItems: agenda?.dueItems || [],
    deferredItems: agenda?.deferredItems || [],
    reopenedItems: agenda?.reopenedItems || [],
    managerAgendaThroughput: agenda?.throughput || null,
    meaningfulProgressSummary:
      progressLines.length > 0
        ? progressLines.join(" | ")
        : "No new cross-session progress markers are visible beyond the current digest anchor.",
    unresolvedGovernanceItems:
      blockerLines.length > 0
        ? blockerLines
        : ["No unresolved governance or stop-condition item is newly highlighted beyond the current digest anchor."],
    recommendedNextAction: recommendation
      ? {
          label: asText(recommendation.label, "Review current shell agenda"),
          detail: asText(
            recommendation.detail,
            "Open the current queue leader before lower-priority portfolio work.",
          ),
          targetSessionId: asText(recommendation.targetSessionId),
          targetCardKey: asText(recommendation.targetCardKey),
        }
      : null,
    nextBestActions: recommendationShortlist(recommendation).map((card) => ({
      session_id: asText(card?.session_id),
      session_handle: asText(card?.session_handle),
      next_action_label: asText(card?.shortcut_action_label || card?.next_action_label),
      current_blocker: asText(card?.current_blocker),
    })),
  };
}

export function buildPortfolioDeferredWorkloadDigest(
  cards = [],
  recommendation = null,
  memory,
  options = {},
) {
  const currentMemory = loadPortfolioDigestMemory(memory);
  const agenda = buildPortfolioManagerAgenda(cards, recommendation, currentMemory, options);
  const anchorSnapshot =
    currentMemory.last_manager_check_snapshot || currentMemory.last_manager_touch_snapshot || null;
  const anchorRecordedAt =
    asText(anchorSnapshot?.recorded_at) ||
    asText(currentMemory.last_manager_check_at || currentMemory.last_manager_touch_at);
  const anchorMs = parseDateMs(anchorRecordedAt);
  const managerEventsSinceCheck = (currentMemory.manager_item_events || []).filter((event) => {
    const eventMs = parseDateMs(event?.at);
    if (!eventMs) {
      return false;
    }
    return anchorMs ? eventMs >= anchorMs : true;
  });

  const deferredItems = Array.isArray(agenda?.deferredItems) ? agenda.deferredItems : [];
  const dueItems = Array.isArray(agenda?.dueItems) ? agenda.dueItems : [];
  const reopenedItems = Array.isArray(agenda?.reopenedItems) ? agenda.reopenedItems : [];
  const overdueAfterReturnItems = (Array.isArray(agenda?.overdueItems) ? agenda.overdueItems : []).filter(
    (card) => asText(card?.agenda_state_key) === "overdue_after_return",
  );
  const deferredWorkloadItems = dedupeCardsBySessionId([
    ...deferredItems,
    ...dueItems,
    ...reopenedItems,
    ...overdueAfterReturnItems,
  ]);
  const deferredHistorySessionIds = new Set([
    ...Object.keys(currentMemory.manager_items || {}),
    ...(currentMemory.manager_item_events || []).map((event) => asText(event?.session_id)).filter(Boolean),
  ]);
  const completedDeferredItems = (Array.isArray(agenda?.completedItems) ? agenda.completedItems : []).filter(
    (item) => deferredHistorySessionIds.has(asText(item?.session_id)),
  );
  const deferredPendingFromBeforeCheck = deferredWorkloadItems.filter((card) => {
    const deferredAtMs = parseDateMs(card?.manager_deferred_at);
    const reopenedAtMs = parseDateMs(card?.manager_reopened_at);
    return (
      (anchorMs && deferredAtMs && deferredAtMs < anchorMs) ||
      (anchorMs && reopenedAtMs && reopenedAtMs < anchorMs)
    );
  }).length;
  const deferredSinceLastCheck = asNumber(agenda?.counts?.deferred_since_last_check, 0);
  const dueReturnedSinceLastCheck = asNumber(
    agenda?.counts?.due_returned_since_last_check,
    asNumber(agenda?.counts?.returned_from_snooze_since_last_check, 0),
  );
  const reopenedSinceLastCheck = asNumber(agenda?.counts?.reopened_since_last_check, 0);
  const overdueAfterReturnSinceLastCheck = managerEventsSinceCheck.filter(
    (event) => asText(event?.event_type) === "overdue_after_return",
  ).length;
  const totalDeferredItems = deferredWorkloadItems.length;
  const basisItems = [
    {
      key: MANAGER_SNOOZE_NEXT_CHECK_KEY,
      label: MANAGER_SNOOZE_NEXT_CHECK_LABEL,
      count: deferredWorkloadItems.filter(
        (item) => asText(item?.manager_defer_basis_key) === MANAGER_SNOOZE_NEXT_CHECK_KEY,
      ).length,
      detail:
        "These items come back automatically at the next explicit manager check and can surface as due-now or overdue-after-return work if they remain unresolved.",
    },
    {
      key: MANAGER_SNOOZE_UNTIL_REOPEN_KEY,
      label: MANAGER_SNOOZE_UNTIL_REOPEN_LABEL,
      count: deferredWorkloadItems.filter(
        (item) => asText(item?.manager_defer_basis_key) === MANAGER_SNOOZE_UNTIL_REOPEN_KEY,
      ).length,
      detail:
        "These items stay parked until the operator reopens them explicitly, so they add deferred pressure without auto-returning on the next manager check.",
    },
  ];
  const nextManagerCheckCount =
    basisItems.find((item) => item.key === MANAGER_SNOOZE_NEXT_CHECK_KEY)?.count || 0;
  const untilReopenCount =
    basisItems.find((item) => item.key === MANAGER_SNOOZE_UNTIL_REOPEN_KEY)?.count || 0;

  const pressureReasons = [];
  if (deferredSinceLastCheck > 0) {
    pressureReasons.push(
      `Deferred pressure increased because ${pluralize(
        deferredSinceLastCheck,
        "item",
      )} were newly deferred since the last manager check.`,
    );
  }
  if (dueReturnedSinceLastCheck > 0) {
    pressureReasons.push(
      `${pluralize(
        dueReturnedSinceLastCheck,
        "item",
      )} became due after the latest manager check.`,
    );
  }
  if (reopenedSinceLastCheck > 0) {
    pressureReasons.push(
      `${pluralize(reopenedSinceLastCheck, "item")} returned through manual reopen.`,
    );
  }
  if (overdueAfterReturnSinceLastCheck > 0) {
    pressureReasons.push(
      `${pluralize(
        overdueAfterReturnSinceLastCheck,
        "returned item",
        "returned items",
      )} crossed into overdue-after-return.`,
    );
  }
  if (completedDeferredItems.length > 0) {
    pressureReasons.push(
      `Deferred pressure decreased because ${pluralize(
        completedDeferredItems.length,
        "deferred item",
      )} completed.`,
    );
  }
  if (!pressureReasons.length) {
    pressureReasons.push(
      totalDeferredItems > 0
        ? `${pluralize(
            totalDeferredItems,
            "deferred item",
          )} remain in play across the deferred queue and returned agenda states.`
        : "No deferred workload is currently pressuring the shell queue.",
    );
  }

  const deferredCurrentItem =
    isDeferredRelatedAgendaState(asText(agenda?.currentItem?.agenda_state_key))
      ? agenda?.currentItem
      : null;
  const currentReason = deferredCurrentItem
    ? `${agendaSummaryLine(deferredCurrentItem)} · ${asText(
        deferredCurrentItem?.manager_return_reason_label,
        deferredCurrentItem?.agenda_state_detail,
      )}`
    : dueItems[0]
      ? `${agendaSummaryLine(dueItems[0])} · ${asText(
          dueItems[0]?.manager_return_reason_label,
          dueItems[0]?.agenda_state_detail,
        )}`
      : deferredItems[0]
        ? `${agendaSummaryLine(deferredItems[0])} · ${asText(
            deferredItems[0]?.manager_defer_basis_label,
            "Deferred",
          )}`
        : "No deferred-return item currently leads the active agenda.";
  const pressureBand = buildDeferredPressureBand({
    totalDeferredItems,
    dueNow: dueItems.length,
    overdueAfterReturn: overdueAfterReturnItems.length,
    reopenedManually: reopenedItems.length,
    deferredSinceLastCheck,
    dueReturnedSinceLastCheck,
    reopenedSinceLastCheck,
    overdueAfterReturnSinceLastCheck,
    deferredCompletedSinceLastCheck: completedDeferredItems.length,
  });
  const responsePolicy = buildDeferredResponsePolicy({
    pressureBand,
    totalDeferredItems,
    deferredNotYetDue: deferredItems.length,
    dueNow: dueItems.length,
    overdueAfterReturn: overdueAfterReturnItems.length,
    reopenedManually: reopenedItems.length,
    nextManagerCheckCount,
    untilReopenCount,
  });
  const responseOutcome = buildDeferredResponseOutcome({
    previousState:
      currentMemory.last_deferred_response_anchor || anchorSnapshot?.deferred_state || null,
    currentPressureBand: pressureBand,
    currentResponsePolicy: responsePolicy,
    currentCounts: {
      total_deferred_items: totalDeferredItems,
      due_now: dueItems.length,
      overdue_after_return: overdueAfterReturnItems.length,
      reopened_manually: reopenedItems.length,
    },
    recordedAt: asText(options.nowIso || new Date().toISOString()),
  });
  if (responseOutcome?.key === RESPONSE_OUTCOME_IMPROVED_KEY) {
    responsePolicy.detail = `${responsePolicy.detail} The last suggested response appears to have reduced deferred pressure.`;
  } else if (responseOutcome?.key === RESPONSE_OUTCOME_WORSENED_KEY) {
    responsePolicy.detail = `${responsePolicy.detail} Deferred pressure worsened, so the current response now outranks normal backlog handling.`;
  } else if (
    responseOutcome?.key === RESPONSE_OUTCOME_STABLE_KEY &&
    asText(pressureBand.key) === DEFERRED_PRESSURE_HIGH_KEY
  ) {
    responsePolicy.detail = `${responsePolicy.detail} Deferred pressure remains high across checks, so keep overdue-after-return review ahead of new deferred work.`;
  }

  return {
    anchor: {
      basis_key: "since_last_manager_check",
      basis_label: "Since last manager check",
      recorded_at: anchorRecordedAt,
      detail: anchorRecordedAt
        ? `Comparing deferred workload pressure against the last recorded manager check at ${anchorRecordedAt}.`
        : "No prior manager check is stored yet in this browser, so the current deferred workload is acting as the baseline.",
      has_comparison: Boolean(anchorRecordedAt),
    },
    headline:
      totalDeferredItems > 0
        ? `Deferred workload now: ${pluralize(
            totalDeferredItems,
            "item",
          )} in play · ${pluralize(deferredItems.length, "item")} parked · ${pluralize(
            dueItems.length,
            "item",
          )} due now · ${pluralize(overdueAfterReturnItems.length, "item")} overdue after return`
        : "Deferred workload is currently clear.",
    detail: pressureReasons.join(" "),
    currentReason,
    pressureBand,
    responsePolicy,
    responseOutcome,
    counts: {
      total_deferred_items: totalDeferredItems,
      deferred_not_yet_due: deferredItems.length,
      due_now: dueItems.length,
      overdue_after_return: overdueAfterReturnItems.length,
      reopened_manually: reopenedItems.length,
      deferred_completed_since_last_check: completedDeferredItems.length,
      deferred_since_last_check: deferredSinceLastCheck,
      due_returned_since_last_check: dueReturnedSinceLastCheck,
      returned_since_last_check: dueReturnedSinceLastCheck + reopenedSinceLastCheck,
      reopened_since_last_check: reopenedSinceLastCheck,
      overdue_after_return_since_last_check: overdueAfterReturnSinceLastCheck,
      still_pending_from_before_last_check: deferredPendingFromBeforeCheck,
      return_basis_next_manager_check:
        basisItems.find((item) => item.key === MANAGER_SNOOZE_NEXT_CHECK_KEY)?.count || 0,
      return_basis_until_reopen:
        basisItems.find((item) => item.key === MANAGER_SNOOZE_UNTIL_REOPEN_KEY)?.count || 0,
    },
    counters: [
      {
        key: "total_deferred_items",
        label: "Total deferred workload",
        count: totalDeferredItems,
        detail:
          totalDeferredItems > 0
            ? deferredWorkloadItems
                .slice(0, DIGEST_LIST_LIMIT)
                .map((item) =>
                  digestLine(
                    item,
                    asText(
                      item?.manager_return_reason_label,
                      item?.manager_defer_basis_label || item?.agenda_state_label,
                    ),
                  ),
                )
                .join(" | ")
            : "No deferred workload is currently active or parked.",
      },
      {
        key: "deferred_not_yet_due",
        label: "Deferred, not yet due",
        count: deferredItems.length,
        detail:
          deferredItems.length > 0
            ? deferredItems
                .slice(0, DIGEST_LIST_LIMIT)
                .map((item) =>
                  digestLine(item, asText(item?.manager_defer_basis_label, "Deferred")),
                )
                .join(" | ")
            : "No deferred item is currently parked outside the active agenda.",
      },
      {
        key: "due_now",
        label: "Due now",
        count: dueItems.length,
        detail:
          dueItems.length > 0
            ? dueItems
                .slice(0, DIGEST_LIST_LIMIT)
                .map((item) =>
                  digestLine(
                    item,
                    asText(item?.manager_return_reason_label, item?.agenda_state_detail),
                  ),
                )
                .join(" | ")
            : "No deferred item is due to return right now.",
      },
      {
        key: "overdue_after_return",
        label: "Overdue after return",
        count: overdueAfterReturnItems.length,
        detail:
          overdueAfterReturnItems.length > 0
            ? overdueAfterReturnItems
                .slice(0, DIGEST_LIST_LIMIT)
                .map((item) =>
                  digestLine(item, asText(item?.agenda_state_detail, item?.current_blocker)),
                )
                .join(" | ")
            : "No returned deferred item has aged into overdue-after-return.",
      },
      {
        key: "reopened_manually",
        label: "Reopened manually",
        count: reopenedItems.length,
        detail:
          reopenedItems.length > 0
            ? reopenedItems
                .slice(0, DIGEST_LIST_LIMIT)
                .map((item) =>
                  digestLine(item, asText(item?.agenda_state_detail, item?.current_blocker)),
                )
                .join(" | ")
            : "No deferred item is currently active through manual reopen.",
      },
      {
        key: "deferred_completed_since_last_check",
        label: "Deferred completed since last check",
        count: completedDeferredItems.length,
        detail:
          completedDeferredItems.length > 0
            ? completedDeferredItems
                .slice(0, DIGEST_LIST_LIMIT)
                .map((item) =>
                  `${asText(item.session_handle || item.session_id, "session")}: ${asText(
                    item.completion_outcome_label,
                    "Completed since last manager check",
                  )}`,
                )
                .join(" | ")
            : "No previously deferred item completed since the current manager check.",
      },
      {
        key: "returned_since_last_check",
        label: "Returned since last check",
        count: dueReturnedSinceLastCheck + reopenedSinceLastCheck,
        detail:
          dueReturnedSinceLastCheck + reopenedSinceLastCheck > 0
            ? [
                dueReturnedSinceLastCheck > 0
                  ? `${pluralize(
                      dueReturnedSinceLastCheck,
                      "item",
                    )} returned because the next manager check came due.`
                  : "",
                reopenedSinceLastCheck > 0
                  ? `${pluralize(
                      reopenedSinceLastCheck,
                      "item",
                    )} returned because the operator reopened them manually.`
                  : "",
              ]
                .filter(Boolean)
                .join(" ")
            : "No deferred item returned after the current manager-check anchor.",
      },
      {
        key: "still_pending_from_before_last_check",
        label: "Still pending from before last check",
        count: deferredPendingFromBeforeCheck,
        detail:
          deferredPendingFromBeforeCheck > 0
            ? `${pluralize(
                deferredPendingFromBeforeCheck,
                "deferred item",
              )} remained unresolved from before the current manager-check anchor.`
            : "No deferred workload is carrying forward from before the current manager check.",
      },
      {
        key: "overdue_after_return_since_last_check",
        label: "Crossed into overdue after return",
        count: overdueAfterReturnSinceLastCheck,
        detail:
          overdueAfterReturnSinceLastCheck > 0
            ? `${pluralize(
                overdueAfterReturnSinceLastCheck,
                "returned item",
                "returned items",
              )} stayed unresolved through another manager check and now outrank newly due deferred work.`
            : "No returned deferred item crossed into overdue-after-return since the current manager check.",
      },
    ],
    returnBasisSummary: basisItems,
    pressureReasons,
    deferredItems: deferredItems.slice(0, DIGEST_LIST_LIMIT),
    dueItems: dueItems.slice(0, DIGEST_LIST_LIMIT),
    reopenedItems: reopenedItems.slice(0, DIGEST_LIST_LIMIT),
    overdueAfterReturnItems: overdueAfterReturnItems.slice(0, DIGEST_LIST_LIMIT),
  };
}
