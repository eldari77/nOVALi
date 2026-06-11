const FILTER_GROUPS = [
  {
    key: "all",
    label: "All visible",
    description: "Show the full bounded portfolio queue.",
    matches: () => true,
    overlay: false,
  },
  {
    key: "blocking_now",
    label: "Blocking now",
    description: "Sessions that need operator review or intervention now.",
    matches: (card) => card?.queue_bucket === "new_blocking_now",
    overlay: false,
  },
  {
    key: "stale_escalated",
    label: "Stale escalated",
    description: "Already-seen unresolved blockers that have escalated locally.",
    matches: (card) => card?.queue_bucket === "stale_escalated_blocking",
    overlay: false,
  },
  {
    key: "acknowledged_unresolved",
    label: "Acknowledged unresolved",
    description: "Blocking sessions that remain unresolved but are not fresh.",
    matches: (card) => card?.queue_bucket === "acknowledged_unresolved_blocking",
    overlay: false,
  },
  {
    key: "resumable",
    label: "Resumable",
    description: "Sessions that are ready for the next bounded continue action.",
    matches: (card) => card?.queue_bucket === "resumable",
    overlay: false,
  },
  {
    key: "running_waiting",
    label: "Running / waiting",
    description: "Sessions that are currently running or waiting on the runtime.",
    matches: (card) => card?.queue_bucket === "running_waiting",
    overlay: false,
  },
  {
    key: "completed_halted",
    label: "Completed / halted",
    description: "Visible finished history that can be reviewed or demoted.",
    matches: (card) =>
      card?.queue_bucket === "completed_halted" && !Boolean(card?.archived),
    overlay: false,
  },
  {
    key: "archived",
    label: "Archived",
    description: "Sessions intentionally moved out of the primary queue.",
    matches: (card) => Boolean(card?.archived),
    overlay: false,
  },
  {
    key: "shortlisted",
    label: "Shortlisted",
    description: "Locally marked sessions to review next after urgent work.",
    matches: (card) => Boolean(card?.shortlisted),
    overlay: true,
  },
  {
    key: "informational_recent",
    label: "Informational recent",
    description: "Recent history that is visible for context but not urgent.",
    matches: (card) => card?.queue_bucket === "informational_recent",
    overlay: false,
  },
];

function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function cardKey(card) {
  if (!card || typeof card !== "object") {
    return "";
  }
  return String(card.entry_key || card.session_id || "").trim();
}

function dedupeActions(actions) {
  const seen = new Set();
  const deduped = [];
  for (const action of asArray(actions)) {
    if (!action || !action.key) {
      continue;
    }
    if (seen.has(action.key)) {
      continue;
    }
    seen.add(action.key);
    deduped.push(action);
  }
  return deduped;
}

function findCards(cards, predicate) {
  return asArray(cards).filter((card) => predicate(card));
}

function truncateTargets(cards, limit) {
  return asArray(cards)
    .map((card) => ({ card, key: cardKey(card) }))
    .filter((entry) => entry.key)
    .slice(0, limit);
}

function buildBatchAction(key, label, detail, cards, limit, batchAction, filterKey) {
  const targets = truncateTargets(cards, limit);
  if (!targets.length) {
    return null;
  }
  const targetCount = asArray(cards).length;
  const truncated = targetCount > targets.length;
  return {
    key,
    label,
    detail: truncated
      ? `${detail} Acting on the first ${targets.length} session(s) keeps the action bounded; ${targetCount - targets.length} additional matching session(s) remain visible.`
      : detail,
    mode: "portfolio_batch",
    batchAction,
    filterKey,
    safe_in_portfolio: true,
    targetCount,
    targetCardKeys: targets.map((entry) => entry.key),
    targetSessionIds: targets.map((entry) => entry.card.session_id).filter(Boolean),
  };
}

function buildOpenAction(key, label, detail, card, filterKey) {
  if (!card) {
    return null;
  }
  return {
    key,
    label,
    detail,
    mode: "open_session",
    safe_in_portfolio: false,
    filterKey,
    targetCardKey: cardKey(card),
    targetSessionId: card.session_id || "",
  };
}

function buildFocusAction(key, label, detail, filterKey) {
  return {
    key,
    label,
    detail,
    mode: "focus_group",
    filterKey,
    safe_in_portfolio: true,
  };
}

function deriveHeadline(recommendation, dominantAction, counts) {
  if (counts.blocking_now > 0) {
    return {
      title: `${counts.blocking_now} blocking session${counts.blocking_now === 1 ? "" : "s"} need attention now`,
      detail:
        recommendation?.detail ||
        "Open the current blocking queue leader before resumable or housekeeping work because explicit review is the current gate.",
    };
  }
  if (counts.stale_escalated > 0) {
    return {
      title: `${counts.stale_escalated} stale escalated blocker${counts.stale_escalated === 1 ? "" : "s"} still need follow-up`,
      detail:
        recommendation?.detail ||
        "Resolve the oldest escalated blocking session before lower-urgency portfolio chores.",
    };
  }
  if (counts.acknowledged_unresolved > 0) {
    return {
      title: `${counts.acknowledged_unresolved} acknowledged blocker${counts.acknowledged_unresolved === 1 ? "" : "s"} remain unresolved`,
      detail:
        recommendation?.detail ||
        "These sessions have already been seen, but they still need explicit operator action before continuation.",
    };
  }
  if (counts.resumable > 0) {
    return {
      title: `${counts.resumable} resumable session${counts.resumable === 1 ? "" : "s"} are ready for the next bounded step`,
      detail:
        recommendation?.detail ||
        "No review gate is blocking the top candidate right now; opening the next resumable session is the strongest move.",
    };
  }
  if (dominantAction) {
    return {
      title: recommendation?.label || dominantAction.label,
      detail:
        recommendation?.detail ||
        dominantAction.detail ||
        "The manager dashboard has surfaced the next best bounded operator move.",
    };
  }
  return {
    title: "No immediate blocking action is required",
    detail:
      "Use the grouped buckets to review resumable, archived, shortlisted, or informational session history without losing truthful queue state.",
  };
}

export const PORTFOLIO_MANAGER_FILTERS = FILTER_GROUPS.map((group) => ({
  key: group.key,
  label: group.label,
  description: group.description,
  overlay: group.overlay,
}));

export function buildPortfolioManagerDashboard(cards, recommendation, options = {}) {
  const visibleCards = asArray(cards);
  const batchLimit =
    Number.isInteger(options.batchLimit) && options.batchLimit > 0
      ? options.batchLimit
      : 4;

  const groupedCounts = FILTER_GROUPS.filter((group) => group.key !== "all").map((group) => ({
    key: group.key,
    label: group.label,
    description: group.description,
    count: findCards(visibleCards, group.matches).length,
    overlay: group.overlay,
  }));

  const countByKey = groupedCounts.reduce((memo, group) => {
    memo[group.key] = group.count;
    return memo;
  }, {});

  const blockingCards = findCards(visibleCards, (card) => card?.queue_bucket === "new_blocking_now");
  const staleCards = findCards(
    visibleCards,
    (card) => card?.queue_bucket === "stale_escalated_blocking",
  );
  const acknowledgedCards = findCards(
    visibleCards,
    (card) => card?.queue_bucket === "acknowledged_unresolved_blocking",
  );
  const resumableCards = findCards(visibleCards, (card) => card?.queue_bucket === "resumable");
  const runningCards = findCards(visibleCards, (card) => card?.queue_bucket === "running_waiting");
  const completedCards = findCards(
    visibleCards,
    (card) => card?.queue_bucket === "completed_halted" && !card?.archived,
  );
  const archivedCards = findCards(visibleCards, (card) => Boolean(card?.archived));
  const shortlistedCards = findCards(visibleCards, (card) => Boolean(card?.shortlisted));

  const dominantAction =
    buildOpenAction(
      "open_blocking_leader",
      recommendation?.label || "Open blocking session needing review",
      "Requires session-level review context. This opens the current blocking queue leader at the exact packet/action without approving anything automatically.",
      blockingCards[0],
      "blocking_now",
    ) ||
    buildOpenAction(
      "open_stale_escalated",
      recommendation?.label || "Open stale escalated blocker",
      "Requires session-level review context. This opens the oldest escalated blocking session so you can resolve it explicitly.",
      staleCards[0],
      "stale_escalated",
    ) ||
    buildOpenAction(
      "open_acknowledged_blocker",
      recommendation?.label || "Open acknowledged unresolved blocker",
      "Requires session-level review context. This opens the blocker that still needs explicit operator resolution.",
      acknowledgedCards[0],
      "acknowledged_unresolved",
    ) ||
    buildOpenAction(
      "open_next_resumable",
      recommendation?.label || "Open next resumable session",
      "Open the highest-priority resumable session and land on the correct bounded continuation control.",
      resumableCards[0],
      "resumable",
    ) ||
    buildFocusAction(
      "focus_shortlist",
      recommendation?.label || "Review shortlist",
      "Focus the shortlist bucket to decide which non-urgent candidate should be handled after current blockers.",
      "shortlisted",
    ) ||
    buildBatchAction(
      "archive_completed_history",
      "Archive completed history",
      "Safe here in the portfolio. This archives completed or non-actionable history without touching active blocking truth.",
      completedCards,
      batchLimit,
      "archive_selected",
      "all",
    ) ||
    buildBatchAction(
      "restore_archived_sessions",
      "Restore archived sessions",
      "Safe here in the portfolio. This restores archived cards to truthful visible buckets without changing session lineage.",
      archivedCards,
      batchLimit,
      "restore_selected",
      "all",
    );

  const followupActions = dedupeActions([
    blockingCards.length > 1
      ? buildFocusAction(
          "review_top_blockers",
          "Review top blockers",
          "Focus the blocking bucket to compare current review-gated sessions before opening one.",
          "blocking_now",
        )
      : null,
    staleCards.length
      ? buildOpenAction(
          "open_escalated_followup",
          "Open stale unresolved blocker",
          "Open the escalated blocker directly from the manager dashboard without losing same-session truth.",
          staleCards[0],
          "stale_escalated",
        )
      : null,
    acknowledgedCards.length
      ? buildFocusAction(
          "focus_acknowledged_unresolved",
          "Review acknowledged unresolved",
          "Focus unresolved-but-already-seen blockers so they stay separate from brand-new blocking work.",
          "acknowledged_unresolved",
        )
      : null,
    resumableCards.length > 1
      ? buildFocusAction(
          "focus_resumable_sessions",
          "Review resumable sessions",
          "Focus the resumable bucket before choosing the next bounded continue action.",
          "resumable",
        )
      : null,
    shortlistedCards.length
      ? buildFocusAction(
          "review_shortlist",
          "Review shortlist",
          "Focus the shortlist overlay to compare the locally-marked follow-up sessions.",
          "shortlisted",
        )
      : null,
  ]).filter((action) => action && action.key !== dominantAction?.key);

  const housekeepingActions = dedupeActions([
    buildBatchAction(
      "archive_completed_history",
      "Archive completed history",
      "Safe here in the portfolio. This archives completed or non-actionable history without touching active blocking truth.",
      completedCards,
      batchLimit,
      "archive_selected",
      "all",
    ),
    buildBatchAction(
      "restore_archived_sessions",
      "Restore archived sessions",
      "Safe here in the portfolio. This restores archived cards to truthful visible buckets without changing session lineage.",
      archivedCards,
      batchLimit,
      "restore_selected",
      "all",
    ),
    buildBatchAction(
      "pin_priority_sessions",
      "Pin priority sessions",
      "Safe here in the portfolio. This pins the current blocking or resumable leaders without changing urgency or execution state.",
      [...blockingCards, ...resumableCards].filter((card) => !card?.pinned),
      batchLimit,
      "pin_selected",
      "all",
    ),
    shortlistedCards.length
      ? buildFocusAction(
          "focus_shortlist_housekeeping",
          "Review shortlist",
          "Focus the shortlist overlay before changing any local portfolio memory.",
          "shortlisted",
        )
      : null,
  ]).filter((action) => action && action.key !== dominantAction?.key);

  const summaryActions = dedupeActions([
    dominantAction,
    ...followupActions.slice(0, 2),
    ...housekeepingActions.slice(0, 3),
  ]);

  const headline = deriveHeadline(recommendation, dominantAction, {
    blocking_now: countByKey.blocking_now || 0,
    stale_escalated: countByKey.stale_escalated || 0,
    acknowledged_unresolved: countByKey.acknowledged_unresolved || 0,
    resumable: countByKey.resumable || 0,
  });

  return {
    groupedCounts,
    dashboardSummary: {
      title: headline.title,
      detail: headline.detail,
      dominantAction,
      followupActions: followupActions.slice(0, 3),
      housekeepingActions: housekeepingActions.slice(0, 3),
      recommendationLabel: recommendation?.label || dominantAction?.label || "",
      recommendationDetail: recommendation?.detail || headline.detail,
    },
    summaryActions,
  };
}

export function filterPortfolioSections(sections, filterKey) {
  if (!filterKey || filterKey === "all") {
    return {
      sections: asArray(sections),
      cards: asArray(sections).flatMap((section) => asArray(section?.cards)),
    };
  }

  const group = FILTER_GROUPS.find((entry) => entry.key === filterKey);
  if (!group) {
    return {
      sections: asArray(sections),
      cards: asArray(sections).flatMap((section) => asArray(section?.cards)),
    };
  }

  const filteredSections = asArray(sections)
    .map((section) => ({
      ...section,
      cards: asArray(section?.cards).filter(group.matches),
    }))
    .filter((section) => section.cards.length > 0);

  return {
    sections: filteredSections,
    cards: filteredSections.flatMap((section) => section.cards),
  };
}
