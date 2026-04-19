import test from "node:test";
import assert from "node:assert/strict";

import {
  buildPortfolioManagerDashboard,
  filterPortfolioSections,
} from "../src/lib/portfolioDashboard.js";

function makeCard(overrides = {}) {
  return {
    entry_key: overrides.entry_key || overrides.session_id || "entry",
    session_id: overrides.session_id || "session",
    session_handle: overrides.session_handle || overrides.session_id || "session",
    queue_bucket: overrides.queue_bucket || "informational_recent",
    lifecycle_section: overrides.lifecycle_section || "recent",
    archived: Boolean(overrides.archived),
    shortlisted: Boolean(overrides.shortlisted),
    pinned: Boolean(overrides.pinned),
    ...overrides,
  };
}

const blockingCard = makeCard({
  entry_key: "blocking-entry",
  session_id: "session-blocking",
  queue_bucket: "new_blocking_now",
  lifecycle_section: "active",
});

const staleCard = makeCard({
  entry_key: "stale-entry",
  session_id: "session-stale",
  queue_bucket: "stale_escalated_blocking",
  lifecycle_section: "recent",
});

const acknowledgedCard = makeCard({
  entry_key: "ack-entry",
  session_id: "session-ack",
  queue_bucket: "acknowledged_unresolved_blocking",
  lifecycle_section: "recent",
});

const resumableCard = makeCard({
  entry_key: "resume-entry",
  session_id: "session-resume",
  queue_bucket: "resumable",
  lifecycle_section: "active",
});

const completedCard = makeCard({
  entry_key: "done-entry",
  session_id: "session-done",
  queue_bucket: "completed_halted",
  lifecycle_section: "recent",
});

const archivedCard = makeCard({
  entry_key: "archived-entry",
  session_id: "session-archived",
  queue_bucket: "completed_halted",
  lifecycle_section: "archived",
  archived: true,
});

const shortlistedInfoCard = makeCard({
  entry_key: "shortlist-entry",
  session_id: "session-shortlist",
  queue_bucket: "informational_recent",
  lifecycle_section: "recent",
  shortlisted: true,
});

const sections = [
  {
    key: "active",
    label: "Active queue",
    detail: "Active sessions.",
    cards: [blockingCard, resumableCard],
  },
  {
    key: "recent",
    label: "Recent",
    detail: "Recent sessions.",
    cards: [staleCard, acknowledgedCard, completedCard, shortlistedInfoCard],
  },
  {
    key: "archived",
    label: "Archived",
    detail: "Archived sessions.",
    cards: [archivedCard],
  },
];

test("grouped dashboard counts remain truthful by session state", () => {
  const dashboard = buildPortfolioManagerDashboard([
    blockingCard,
    staleCard,
    acknowledgedCard,
    resumableCard,
    completedCard,
    archivedCard,
    shortlistedInfoCard,
  ]);
  const counts = Object.fromEntries(
    dashboard.groupedCounts.map((group) => [group.key, group.count]),
  );

  assert.equal(counts.blocking_now, 1);
  assert.equal(counts.stale_escalated, 1);
  assert.equal(counts.acknowledged_unresolved, 1);
  assert.equal(counts.resumable, 1);
  assert.equal(counts.completed_halted, 1);
  assert.equal(counts.archived, 1);
  assert.equal(counts.shortlisted, 1);
  assert.equal(counts.informational_recent, 1);
});

test("dominant recommendation logic remains explainable and stable", () => {
  const dashboard = buildPortfolioManagerDashboard(
    [blockingCard, resumableCard, completedCard],
    {
      label: "Open blocking session needing review",
      detail:
        "Open the current blocking queue leader before resumable or housekeeping work because explicit review is the gate.",
    },
  );

  assert.equal(dashboard.dashboardSummary.dominantAction.key, "open_blocking_leader");
  assert.equal(
    dashboard.dashboardSummary.dominantAction.targetSessionId,
    "session-blocking",
  );
  assert.match(
    dashboard.dashboardSummary.detail,
    /blocking queue leader|review/i,
  );
});

test("shortlist and grouped summary actions preserve session lineage and history targets", () => {
  const dashboard = buildPortfolioManagerDashboard([
    blockingCard,
    completedCard,
    archivedCard,
    shortlistedInfoCard,
  ]);

  const archiveAction = dashboard.summaryActions.find(
    (action) => action.key === "archive_completed_history",
  );
  const restoreAction = dashboard.summaryActions.find(
    (action) => action.key === "restore_archived_sessions",
  );

  assert.ok(archiveAction);
  assert.deepEqual(archiveAction.targetCardKeys, ["done-entry"]);
  assert.deepEqual(archiveAction.targetSessionIds, ["session-done"]);

  assert.ok(restoreAction);
  assert.deepEqual(restoreAction.targetCardKeys, ["archived-entry"]);
  assert.deepEqual(restoreAction.targetSessionIds, ["session-archived"]);
});

test("grouped actions do not hide current blockers", () => {
  const dashboard = buildPortfolioManagerDashboard([
    blockingCard,
    completedCard,
    archivedCard,
  ]);
  const archiveAction = dashboard.summaryActions.find(
    (action) => action.key === "archive_completed_history",
  );

  assert.ok(archiveAction);
  assert.deepEqual(archiveAction.targetSessionIds, ["session-done"]);
  assert.ok(!archiveAction.targetSessionIds.includes("session-blocking"));

  const filtered = filterPortfolioSections(sections, "completed_halted");
  assert.deepEqual(
    filtered.cards.map((card) => card.session_id),
    ["session-done"],
  );
});

test("deep-link from dashboard action still lands on the correct session and packet target", () => {
  const dashboard = buildPortfolioManagerDashboard([
    blockingCard,
    staleCard,
    resumableCard,
  ]);
  const dominant = dashboard.dashboardSummary.dominantAction;

  assert.equal(dominant.mode, "open_session");
  assert.equal(dominant.filterKey, "blocking_now");
  assert.equal(dominant.targetCardKey, "blocking-entry");
  assert.equal(dominant.targetSessionId, "session-blocking");
});

test("same-session continuation targeting stays stable after dashboard-based navigation", () => {
  const dashboard = buildPortfolioManagerDashboard([
    resumableCard,
    shortlistedInfoCard,
  ]);
  const dominant = dashboard.dashboardSummary.dominantAction;

  assert.equal(dominant.key, "open_next_resumable");
  assert.equal(dominant.mode, "open_session");
  assert.equal(dominant.targetCardKey, "resume-entry");
  assert.equal(dominant.targetSessionId, "session-resume");
});
