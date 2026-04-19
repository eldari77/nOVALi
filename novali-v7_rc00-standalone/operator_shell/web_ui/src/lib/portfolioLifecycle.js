import { buildPortfolioRecommendation } from "./sessionPortfolio.js";

const PRIMARY_RECENT_LIMIT = 4;
const HISTORICAL_RECENT_LIMIT = 4;
const ARCHIVED_SESSION_LIMIT = 8;
const ACTIONABLE_BUCKETS = new Set([
  "new_blocking_now",
  "stale_escalated_blocking",
  "seen_unresolved_blocking",
  "acknowledged_unresolved_blocking",
  "resumable",
  "running_waiting",
]);

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

function parseDateMs(value) {
  const raw = asText(value);
  if (!raw) {
    return 0;
  }
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : 0;
}

function lifecycleTimestamp() {
  return new Date().toISOString();
}

function normalizeLifecycleState(sessionState) {
  return {
    pinned: Boolean(sessionState?.pinned),
    archived: Boolean(sessionState?.archived),
    pinned_at: asText(sessionState?.pinned_at),
    archived_at: asText(sessionState?.archived_at),
    updated_at: asText(sessionState?.updated_at),
  };
}

export function createEmptyPortfolioLifecycleMemory() {
  return {
    schema_version: 1,
    sessions: {},
  };
}

export function loadPortfolioLifecycleMemory(raw) {
  if (!raw) {
    return createEmptyPortfolioLifecycleMemory();
  }
  try {
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!parsed || typeof parsed !== "object") {
      return createEmptyPortfolioLifecycleMemory();
    }
    const sessions =
      parsed.sessions && typeof parsed.sessions === "object"
        ? Object.fromEntries(
            Object.entries(parsed.sessions).map(([sessionId, sessionState]) => [
              sessionId,
              normalizeLifecycleState(sessionState),
            ]),
          )
        : {};
    return {
      schema_version: 1,
      sessions,
    };
  } catch {
    return createEmptyPortfolioLifecycleMemory();
  }
}

export function serializePortfolioLifecycleMemory(memory) {
  return JSON.stringify(memory || createEmptyPortfolioLifecycleMemory());
}

export function isActionablePortfolioCard(card) {
  return ACTIONABLE_BUCKETS.has(asText(card?.queue_bucket));
}

export function canArchivePortfolioCard(card) {
  return !isActionablePortfolioCard(card);
}

export function canPinPortfolioCard(card) {
  return Boolean(asText(card?.session_id)) && !Boolean(card?.archived);
}

function lifecycleLabelFromSection(sectionKey) {
  if (sectionKey === "active") return "Active queue";
  if (sectionKey === "pinned") return "Pinned";
  if (sectionKey === "recent") return "Recent";
  if (sectionKey === "historical") return "Historical recent";
  if (sectionKey === "archived") return "Archived";
  return "Recent";
}

function lifecycleToneFromSection(sectionKey) {
  if (sectionKey === "active") return "warning";
  if (sectionKey === "pinned") return "info";
  if (sectionKey === "archived") return "phase";
  return "success";
}

function decorateLifecycleCard(card, memory) {
  const lifecycleState = normalizeLifecycleState(
    memory?.sessions?.[asText(card?.session_id)] || {},
  );
  const actionable = isActionablePortfolioCard(card);
  return {
    ...card,
    pinned: lifecycleState.pinned,
    archived: lifecycleState.archived,
    pinned_at: lifecycleState.pinned_at,
    archived_at: lifecycleState.archived_at,
    lifecycle_updated_at: lifecycleState.updated_at,
    actionable_session: actionable,
    can_archive: canArchivePortfolioCard(card),
    can_pin: canPinPortfolioCard({ ...card, archived: lifecycleState.archived }),
    pin_action_label: lifecycleState.pinned ? "Unpin session" : "Pin session",
    archive_action_label: lifecycleState.archived ? "Restore session" : "Archive session",
    lifecycle_blocked_reason: actionable
      ? "Blocking, resumable, or running sessions stay discoverable until backend truth changes."
      : "",
  };
}

function withLifecycleSection(card, sectionKey) {
  return {
    ...card,
    lifecycle_section: sectionKey,
    lifecycle_section_label: lifecycleLabelFromSection(sectionKey),
    lifecycle_section_tone: lifecycleToneFromSection(sectionKey),
  };
}

export function applyPortfolioLifecycleAction(memory, card, action) {
  const currentMemory = loadPortfolioLifecycleMemory(memory);
  const sessionId = asText(card?.session_id);
  if (!sessionId) {
    return {
      memory: currentMemory,
      changed: false,
      blocked_reason: "No truthful session id is available for this portfolio card.",
      notice: "",
      session_state: null,
    };
  }

  const now = lifecycleTimestamp();
  const currentState = normalizeLifecycleState(currentMemory.sessions?.[sessionId] || {});
  let nextState = { ...currentState };
  let notice = "";

  if (action === "pin") {
    if (currentState.archived) {
      return {
        memory: currentMemory,
        changed: false,
        blocked_reason: "Restore the archived session before pinning it.",
        notice: "",
        session_state: currentState,
      };
    }
    nextState.pinned = true;
    nextState.pinned_at = now;
    nextState.updated_at = now;
    notice = "Session pinned in the portfolio. Its urgency stays backend-derived.";
  } else if (action === "unpin") {
    nextState.pinned = false;
    nextState.updated_at = now;
    notice = "Session unpinned from the portfolio watchlist.";
  } else if (action === "archive") {
    if (isActionablePortfolioCard(card)) {
      return {
        memory: currentMemory,
        changed: false,
        blocked_reason:
          "This session still has a truthful actionable state, so it remains discoverable in the active queue.",
        notice: "",
        session_state: currentState,
      };
    }
    nextState.archived = true;
    nextState.archived_at = now;
    nextState.updated_at = now;
    nextState.pinned = false;
    notice =
      "Session archived from the primary queue. Truthful lineage and history remain available in the archive section.";
  } else if (action === "restore") {
    nextState.archived = false;
    nextState.updated_at = now;
    notice = "Archived session restored to the non-archived portfolio view.";
  } else {
    return {
      memory: currentMemory,
      changed: false,
      blocked_reason: "Unsupported portfolio lifecycle action.",
      notice: "",
      session_state: currentState,
    };
  }

  currentMemory.sessions = {
    ...currentMemory.sessions,
    [sessionId]: nextState,
  };
  return {
    memory: currentMemory,
    changed: true,
    blocked_reason: "",
    notice,
    session_state: nextState,
  };
}

function sortByUpdatedAt(left, right, secondaryField = "updated_at_ms") {
  return (
    asNumber(right?.[secondaryField], 0) - asNumber(left?.[secondaryField], 0) ||
    asNumber(right?.queue_rank, 0) - asNumber(left?.queue_rank, 0)
  );
}

export function buildManagedSessionPortfolio(cards, recommendation, memory, options = {}) {
  const currentMemory = loadPortfolioLifecycleMemory(memory);
  const normalizedCards = Array.isArray(cards)
    ? cards.map((card) =>
        decorateLifecycleCard(card, currentMemory),
      )
    : [];

  const actionableCards = normalizedCards
    .filter((card) => !card.archived && card.actionable_session)
    .map((card) => withLifecycleSection(card, "active"));

  const pinnedCards = normalizedCards
    .filter((card) => !card.archived && card.pinned && !card.actionable_session)
    .sort(sortByUpdatedAt)
    .slice(0, PRIMARY_RECENT_LIMIT)
    .map((card) => withLifecycleSection(card, "pinned"));

  const recentCandidates = normalizedCards
    .filter((card) => !card.archived && !card.pinned && !card.actionable_session)
    .sort(sortByUpdatedAt);

  const recentCards = recentCandidates
    .slice(0, PRIMARY_RECENT_LIMIT)
    .map((card) => withLifecycleSection(card, "recent"));

  const historicalCards = recentCandidates
    .slice(PRIMARY_RECENT_LIMIT, PRIMARY_RECENT_LIMIT + HISTORICAL_RECENT_LIMIT)
    .map((card) => withLifecycleSection(card, "historical"));

  const archivedCards = normalizedCards
    .filter((card) => card.archived)
    .sort(
      (left, right) =>
        parseDateMs(right.archived_at) - parseDateMs(left.archived_at) ||
        sortByUpdatedAt(left, right),
    )
    .slice(0, ARCHIVED_SESSION_LIMIT)
    .map((card) => withLifecycleSection(card, "archived"));

  const visibleNonArchivedCards = [...actionableCards, ...pinnedCards, ...recentCards, ...historicalCards];
  const recommendationSourceCards =
    actionableCards.length > 0 ? actionableCards : visibleNonArchivedCards;
  const nextRecommendation =
    recommendationSourceCards.length > 0
      ? buildPortfolioRecommendation(recommendationSourceCards, options)
      : recommendation;

  const sections = [
    {
      key: "active",
      label: "Current action queue",
      detail:
        "Blocking, resumable, and running sessions stay here even when you pin or archive other cards.",
      cards: actionableCards,
    },
    {
      key: "pinned",
      label: "Pinned sessions",
      detail:
        "Pinned sessions stay easy to find without outranking a truthful current blocker.",
      cards: pinnedCards,
    },
    {
      key: "recent",
      label: "Recent session history",
      detail:
        "Recent non-actionable sessions stay reviewable here before they fall into older historical context.",
      cards: recentCards,
    },
    {
      key: "historical",
      label: "Historical recent sessions",
      detail:
        "Older recent sessions remain bounded and reviewable without crowding the primary queue.",
      cards: historicalCards,
    },
    {
      key: "archived",
      label: "Archived sessions",
      detail:
        "Archived sessions stay truthful and recoverable here while leaving the primary queue focused on current work.",
      cards: archivedCards,
    },
  ].filter((section) => section.cards.length > 0);

  const bucketCounts = normalizedCards.reduce((accumulator, card) => {
    const bucket = asText(card.queue_bucket, "clear");
    accumulator[bucket] = asNumber(accumulator[bucket], 0) + (card.archived ? 0 : 1);
    return accumulator;
  }, {});

  return {
    sections,
    all_visible_cards: [...visibleNonArchivedCards, ...archivedCards],
    recommendation: nextRecommendation,
    bucket_counts: bucketCounts,
    counts: {
      active: actionableCards.length,
      pinned: pinnedCards.length,
      recent: recentCards.length,
      historical: historicalCards.length,
      archived: archivedCards.length,
      archived_total: normalizedCards.filter((card) => card.archived).length,
      recent_overflow: Math.max(recentCandidates.length - PRIMARY_RECENT_LIMIT, 0),
      visible_non_archived: visibleNonArchivedCards.length,
    },
    retention_rules: {
      recent_visible_limit: PRIMARY_RECENT_LIMIT,
      historical_visible_limit: HISTORICAL_RECENT_LIMIT,
      archived_visible_limit: ARCHIVED_SESSION_LIMIT,
    },
  };
}
