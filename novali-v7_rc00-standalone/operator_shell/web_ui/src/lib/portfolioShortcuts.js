import {
  canArchivePortfolioCard,
  canPinPortfolioCard,
  isActionablePortfolioCard,
} from "./portfolioLifecycle.js";

export const PORTFOLIO_BATCH_SELECTION_LIMIT = 4;

const BLOCKING_BUCKETS = new Set([
  "new_blocking_now",
  "stale_escalated_blocking",
  "seen_unresolved_blocking",
  "acknowledged_unresolved_blocking",
]);
const SESSION_OPEN_BUCKETS = new Set([
  ...BLOCKING_BUCKETS,
  "resumable",
  "running_waiting",
]);
const SHORTLIST_ENTRY_LIMIT = 12;

function asText(value, fallback = "") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function timestamp() {
  return new Date().toISOString();
}

function parseDateMs(value) {
  const parsed = Date.parse(asText(value));
  return Number.isFinite(parsed) ? parsed : 0;
}

function shortlistKey(card) {
  return asText(card?.entry_key) || asText(card?.session_id);
}

function normalizeShortcutState(state) {
  return {
    shortlisted: Boolean(state?.shortlisted),
    updated_at: asText(state?.updated_at),
  };
}

function pruneShortcutMemory(memory) {
  const next = clone(memory);
  const entries = Object.entries(next.sessions || {})
    .map(([key, state]) => [key, normalizeShortcutState(state)])
    .filter(([, state]) => state.shortlisted);
  if (entries.length <= SHORTLIST_ENTRY_LIMIT) {
    next.sessions = Object.fromEntries(entries);
    return next;
  }
  entries.sort((left, right) => parseDateMs(right[1].updated_at) - parseDateMs(left[1].updated_at));
  next.sessions = Object.fromEntries(entries.slice(0, SHORTLIST_ENTRY_LIMIT));
  return next;
}

function firstLifecycleBlockedReason(cards = [], fallback) {
  for (const card of cards) {
    const reason = asText(card?.lifecycle_blocked_reason);
    if (reason) {
      return reason;
    }
  }
  return fallback;
}

function isSessionOpenShortcut(card) {
  return SESSION_OPEN_BUCKETS.has(asText(card?.queue_bucket));
}

function buildShortcut(card) {
  const queueBucket = asText(card?.queue_bucket);
  if (card?.archived) {
    return {
      key: "restore",
      label: "Restore to queue",
      detail: "Safe here in the portfolio. Restoring keeps the same session lineage and returns this card to a truthful visible bucket.",
      mode: "direct",
      tone: "secondary",
      requires_session_open: false,
    };
  }
  if (BLOCKING_BUCKETS.has(queueBucket)) {
    return {
      key: "open_blocker",
      label: "Resolve blocker",
      detail: "Requires session-level review context. This shortcut opens the exact blocking packet/action without approving anything automatically.",
      mode: "open_session",
      tone: "warning",
      requires_session_open: true,
    };
  }
  if (queueBucket === "resumable") {
    return {
      key: "open_resumable",
      label: "Continue session",
      detail: "Requires the session workspace. This shortcut opens continuation controls for the same session id.",
      mode: "open_session",
      tone: "warning",
      requires_session_open: true,
    };
  }
  if (queueBucket === "running_waiting") {
    return {
      key: "open_running",
      label: "Open running session",
      detail: "Opens the live session summary without starting a new session or changing execution state from the portfolio.",
      mode: "open_session",
      tone: "secondary",
      requires_session_open: true,
    };
  }
  if (canArchivePortfolioCard(card)) {
    return {
      key: "archive",
      label: "Archive from queue",
      detail: "Safe here in the portfolio. Archiving removes non-actionable clutter from the primary queue while preserving lineage, blocker text, CTA text, and restore path.",
      mode: "direct",
      tone: "secondary",
      requires_session_open: false,
    };
  }
  return {
    key: "open_summary",
    label: asText(card?.open_action_label, "View session summary"),
    detail: isSessionOpenShortcut(card)
      ? "This remains a session-level action and opens the correct surface without creating a hidden new session."
      : "This entry is history-first. Keep it in the portfolio or open the summary for more context.",
    mode: isSessionOpenShortcut(card) ? "open_session" : "history",
    tone: "secondary",
    requires_session_open: isSessionOpenShortcut(card),
  };
}

function decorateCard(card, memory) {
  const key = shortlistKey(card);
  const shortcutState = normalizeShortcutState(memory?.sessions?.[key]);
  const shortcut = buildShortcut(card);
  return {
    ...card,
    shortlist_key: key,
    shortlisted: shortcutState.shortlisted,
    shortlist_action_label: shortcutState.shortlisted
      ? "Remove from review next"
      : "Shortlist for review next",
    shortcut_action_key: shortcut.key,
    shortcut_action_label: shortcut.label,
    shortcut_action_detail: shortcut.detail,
    shortcut_action_mode: shortcut.mode,
    shortcut_tone: shortcut.tone,
    shortcut_requires_session_open: shortcut.requires_session_open,
    shortcut_blocked_reason: asText(shortcut.blocked_reason),
    direct_portfolio_actionable: shortcut.mode === "direct",
  };
}

function selectionSummary(cards = []) {
  return cards
    .map((card) => asText(card?.session_handle) || asText(card?.session_id) || "session")
    .slice(0, 3)
    .join(" · ");
}

function buildActionDefinition({ key, label, allowed, blockedReason, detail, selectionCount }) {
  return {
    key,
    label,
    allowed,
    blocked_reason: blockedReason,
    detail,
    selection_count: selectionCount,
  };
}

function buildBatchActions(cards = [], selectedCards = []) {
  const selectionCount = selectedCards.length;
  const archiveReadyCount = cards.filter((card) => !card.archived && canArchivePortfolioCard(card)).length;
  const restoreReadyCount = cards.filter((card) => card.archived).length;
  const pinReadyCount = cards.filter((card) => !card.archived && canPinPortfolioCard(card) && !card.pinned).length;
  const unpinReadyCount = cards.filter((card) => !card.archived && card.pinned).length;
  const shortlistReadyCount = cards.filter((card) => !card.archived && !card.shortlisted).length;
  const clearShortlistReadyCount = cards.filter((card) => !card.archived && card.shortlisted).length;

  const noSelectionReason = "Select one or more portfolio sessions first.";
  const mixedArchivedReason =
    "This selection mixes archived and visible sessions. Use restore on archived sessions first, or limit the selection to one truthful lifecycle state.";
  const mixedPinReason =
    "This selection mixes already-pinned and unpinned sessions. Pin or unpin a consistent set so the batch action stays truthful.";
  const mixedShortlistReason =
    "This selection mixes already-shortlisted and unshortlisted sessions. Use one consistent shortlist action at a time.";

  const actions = {
    pin_selected: buildActionDefinition({
      key: "pin_selected",
      label: "Pin selected",
      allowed:
        selectionCount > 0 &&
        selectedCards.every((card) => !card.archived && !card.pinned && canPinPortfolioCard(card)),
      blockedReason:
        selectionCount === 0
          ? noSelectionReason
          : selectedCards.some((card) => card.archived)
            ? "Archived sessions must be restored before pinning."
            : selectedCards.some((card) => card.pinned)
              ? mixedPinReason
              : firstLifecycleBlockedReason(
                  selectedCards,
                  "Selected sessions cannot all be pinned from the portfolio.",
                ),
      detail: "Safe in portfolio. Pinning improves findability only and does not raise urgency over a true blocker.",
      selectionCount,
    }),
    unpin_selected: buildActionDefinition({
      key: "unpin_selected",
      label: "Unpin selected",
      allowed: selectionCount > 0 && selectedCards.every((card) => !card.archived && card.pinned),
      blockedReason:
        selectionCount === 0
          ? noSelectionReason
          : selectedCards.some((card) => card.archived)
            ? "Archived sessions are already outside the primary queue. Restore them before changing their pinned state."
            : selectedCards.some((card) => !card.pinned)
              ? mixedPinReason
              : "Selected sessions are not all pinned.",
      detail: "Safe in portfolio. Unpinning changes only local queue presentation.",
      selectionCount,
    }),
    archive_selected: buildActionDefinition({
      key: "archive_selected",
      label: "Archive selected",
      allowed:
        selectionCount > 0 &&
        selectedCards.every((card) => !card.archived && canArchivePortfolioCard(card)),
      blockedReason:
        selectionCount === 0
          ? noSelectionReason
          : selectedCards.some((card) => card.archived)
            ? mixedArchivedReason
            : selectedCards.some((card) => isActionablePortfolioCard(card))
              ? "Current blocking, resumable, or running sessions must remain discoverable. Open those sessions instead of archiving them here."
              : firstLifecycleBlockedReason(
                  selectedCards,
                  "Selected sessions cannot all be archived from the portfolio.",
                ),
      detail: "Safe for completed, historical, or informational sessions. Archiving preserves lineage and restore path while clearing primary-queue clutter.",
      selectionCount,
    }),
    restore_selected: buildActionDefinition({
      key: "restore_selected",
      label: "Restore selected",
      allowed: selectionCount > 0 && selectedCards.every((card) => card.archived),
      blockedReason:
        selectionCount === 0
          ? noSelectionReason
          : selectedCards.some((card) => !card.archived)
            ? mixedArchivedReason
            : "Selected sessions are not all archived.",
      detail: "Safe in portfolio. Restoring preserves the same session identity and returns archived cards to truthful visible buckets.",
      selectionCount,
    }),
    shortlist_selected: buildActionDefinition({
      key: "shortlist_selected",
      label: "Shortlist selected",
      allowed: selectionCount > 0 && selectedCards.every((card) => !card.archived && !card.shortlisted),
      blockedReason:
        selectionCount === 0
          ? noSelectionReason
          : selectedCards.some((card) => card.archived)
            ? "Archived sessions must be restored before you shortlist them for review next."
            : selectedCards.some((card) => card.shortlisted)
              ? mixedShortlistReason
              : "Selected sessions are not all eligible for shortlisting.",
      detail: "Safe in portfolio. Shortlisting marks local review-next intent without changing backend urgency or execution state.",
      selectionCount,
    }),
    clear_shortlist_selected: buildActionDefinition({
      key: "clear_shortlist_selected",
      label: "Clear shortlist",
      allowed: selectionCount > 0 && selectedCards.every((card) => !card.archived && card.shortlisted),
      blockedReason:
        selectionCount === 0
          ? noSelectionReason
          : selectedCards.some((card) => card.archived)
            ? "Archived sessions must be restored before shortlist state can be changed."
            : selectedCards.some((card) => !card.shortlisted)
              ? mixedShortlistReason
              : "Selected sessions are not all shortlisted.",
      detail: "Safe in portfolio. Removing shortlist state affects only local operator planning.",
      selectionCount,
    }),
  };

  return {
    selection_count: selectionCount,
    selection_summary: selectionSummary(selectedCards),
    max_selection: PORTFOLIO_BATCH_SELECTION_LIMIT,
    ready_counts: {
      archive_ready: archiveReadyCount,
      restore_ready: restoreReadyCount,
      pin_ready: pinReadyCount,
      unpin_ready: unpinReadyCount,
      shortlist_ready: shortlistReadyCount,
      clear_shortlist_ready: clearShortlistReadyCount,
    },
    actions,
    safe_batch_shortcuts: [
      {
        key: "archive_selected",
        label: "Archive completed / historical sessions",
        eligible_count: archiveReadyCount,
        detail: "Use batch archive only for non-actionable history. Current blockers still require opening the session.",
      },
      {
        key: "restore_selected",
        label: "Restore archived sessions",
        eligible_count: restoreReadyCount,
        detail: "Restore keeps the same session lineage and returns cards to truthful visible buckets.",
      },
      {
        key: "pin_selected",
        label: "Pin / unpin visible sessions",
        eligible_count: pinReadyCount + unpinReadyCount,
        detail: "Pinning is portfolio-only and improves findability without raising urgency over blockers.",
      },
      {
        key: "shortlist_selected",
        label: "Shortlist review-next sessions",
        eligible_count: shortlistReadyCount + clearShortlistReadyCount,
        detail: "Shortlist is local planning memory only. Review-gated continuation approvals still require session-level context.",
      },
    ].filter((shortcut) => shortcut.eligible_count > 0),
  };
}

export function createEmptyPortfolioShortcutMemory() {
  return {
    schema_version: 1,
    sessions: {},
  };
}

export function loadPortfolioShortcutMemory(raw) {
  if (!raw) {
    return createEmptyPortfolioShortcutMemory();
  }
  try {
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!parsed || typeof parsed !== "object") {
      return createEmptyPortfolioShortcutMemory();
    }
    const sessions =
      parsed.sessions && typeof parsed.sessions === "object"
        ? Object.fromEntries(
            Object.entries(parsed.sessions).map(([key, state]) => [
              key,
              normalizeShortcutState(state),
            ]),
          )
        : {};
    return pruneShortcutMemory({
      schema_version: 1,
      sessions,
    });
  } catch {
    return createEmptyPortfolioShortcutMemory();
  }
}

export function serializePortfolioShortcutMemory(memory) {
  return JSON.stringify(pruneShortcutMemory(loadPortfolioShortcutMemory(memory)));
}

export function applyPortfolioShortcutMemoryAction(memory, cards = [], action) {
  const normalizedCards = Array.isArray(cards) ? cards.filter(Boolean) : [];
  if (!normalizedCards.length) {
    return {
      memory: loadPortfolioShortcutMemory(memory),
      changed: false,
      blocked_reason: "Select one or more portfolio sessions before changing shortlist state.",
      notice: "",
    };
  }
  const nextMemory = clone(loadPortfolioShortcutMemory(memory));
  const now = timestamp();
  let changed = false;
  for (const card of normalizedCards) {
    if (card.archived) {
      return {
        memory: nextMemory,
        changed: false,
        blocked_reason: "Archived sessions must be restored before shortlist state can be changed.",
        notice: "",
      };
    }
    const key = shortlistKey(card);
    if (!key) {
      continue;
    }
    const currentState = normalizeShortcutState(nextMemory.sessions[key]);
    const nextShortlisted = action === "shortlist";
    if (currentState.shortlisted === nextShortlisted) {
      continue;
    }
    changed = true;
    if (nextShortlisted) {
      nextMemory.sessions[key] = {
        shortlisted: true,
        updated_at: now,
      };
    } else {
      delete nextMemory.sessions[key];
    }
  }
  const pruned = pruneShortcutMemory(nextMemory);
  return {
    memory: pruned,
    changed,
    blocked_reason: "",
    notice: changed
      ? action === "shortlist"
        ? `${normalizedCards.length} session${normalizedCards.length === 1 ? "" : "s"} added to the review-next shortlist.`
        : `${normalizedCards.length} session${normalizedCards.length === 1 ? "" : "s"} removed from the review-next shortlist.`
      : "",
  };
}

export function buildPortfolioActionView(sections = [], recommendation = null, memory, selectionKeys = []) {
  const shortcutMemory = loadPortfolioShortcutMemory(memory);
  const selectedSet = new Set(
    (Array.isArray(selectionKeys) ? selectionKeys : [])
      .map((value) => asText(value))
      .filter(Boolean),
  );
  const decoratedSections = (Array.isArray(sections) ? sections : []).map((section) => ({
    ...section,
    cards: (Array.isArray(section?.cards) ? section.cards : []).map((card) =>
      decorateCard(card, shortcutMemory),
    ),
  }));
  const cards = decoratedSections.flatMap((section) => section.cards || []);
  const cardByKey = new Map(cards.map((card) => [shortlistKey(card), card]));
  const selectedCards = cards.filter((card) => selectedSet.has(shortlistKey(card)));
  const batch = buildBatchActions(cards, selectedCards);
  const decoratedRecommendation = recommendation
    ? {
        ...recommendation,
        shortlist: (Array.isArray(recommendation?.shortlist) ? recommendation.shortlist : []).map(
          (card) => cardByKey.get(shortlistKey(card)) || decorateCard(card, shortcutMemory),
        ),
      }
    : null;
  return {
    sections: decoratedSections,
    cards,
    recommendation: decoratedRecommendation,
    batch,
    action_rules: [
      {
        key: "portfolio_direct",
        label: "Safe here in portfolio",
        detail:
          "Pin, unpin, archive, restore, and shortlist remain local queue actions only. They do not change backend blocking truth or execution state.",
      },
      {
        key: "requires_session_open",
        label: "Requires opening the session",
        detail:
          "Resolving blockers, approving review-gated continuation, and continuing a resumable session still open the exact session workspace and keep review semantics explicit.",
      },
      {
        key: "blocked_batch_execution",
        label: "Never batched here",
        detail:
          "Review approvals, intervention resolutions, and execution-state changes remain packet-specific. rc72 does not add an approve-everything path across sessions.",
      },
    ],
  };
}
