import test from "node:test";
import assert from "node:assert/strict";

import {
  buildPortfolioDeferredWorkloadDigest,
  buildPortfolioDigestSnapshot,
  buildDeferredResponseAnchorState,
  buildPortfolioManagerAgenda,
  buildPortfolioManagerDigest,
  buildPortfolioOperatorQueue,
  classifyOperatorQueueGroup,
  createEmptyPortfolioDigestMemory,
  deferPortfolioManagerItem,
  reopenPortfolioManagerItem,
  recordDeferredResponseAnchor,
  recordPortfolioDigestTouch,
} from "../src/lib/portfolioDigest.js";

function makeCard(overrides = {}) {
  return {
    entry_key: overrides.entry_key || overrides.session_id || "entry",
    session_id: overrides.session_id || "session",
    session_handle: overrides.session_handle || overrides.session_id || "session",
    queue_bucket: overrides.queue_bucket || "informational_recent_history",
    queue_rank: overrides.queue_rank ?? 50,
    lifecycle_state: overrides.lifecycle_state || "waiting_for_next_invocation",
    lifecycle_section: overrides.lifecycle_section || "recent",
    checkpoint_id: overrides.checkpoint_id || `${overrides.session_id || "session"}::checkpoint::0001`,
    checkpoint_count: overrides.checkpoint_count ?? 1,
    current_cycle: overrides.current_cycle ?? 1,
    current_blocker: overrides.current_blocker || "",
    next_action_label: overrides.next_action_label || "",
    next_action_detail: overrides.next_action_detail || "",
    shortcut_action_label: overrides.shortcut_action_label || "",
    shortcut_action_detail: overrides.shortcut_action_detail || "",
    what_changed_summary: overrides.what_changed_summary || "",
    latest_progress_marker: overrides.latest_progress_marker || "",
    summary_signature: overrides.summary_signature || `${overrides.session_id || "session"}::sig`,
    archived: Boolean(overrides.archived),
    pinned: Boolean(overrides.pinned),
    shortlisted: Boolean(overrides.shortlisted),
    ...overrides,
  };
}

test("operator queue bucket classification remains truthful", () => {
  assert.equal(
    classifyOperatorQueueGroup(
      makeCard({
        session_id: "review-session",
        queue_bucket: "new_blocking_now",
        current_blocker: "Review packet requires action.",
        next_action_label: "Resolve intervention packet",
      }),
    ),
    "pending_review_intervention",
  );
  assert.equal(
    classifyOperatorQueueGroup(
      makeCard({
        session_id: "stale-session",
        queue_bucket: "stale_escalated_blocking",
        next_action_label: "Resolve intervention packet",
      }),
    ),
    "stale_escalated",
  );
  assert.equal(
    classifyOperatorQueueGroup(
      makeCard({
        session_id: "resume-session",
        queue_bucket: "resumable",
        next_action_label: "Continue until next bounded stop",
      }),
    ),
    "resumable",
  );
  assert.equal(
    classifyOperatorQueueGroup(
      makeCard({
        session_id: "done-session",
        queue_bucket: "completed_halted",
        next_action_label: "Review results",
      }),
    ),
    "completed_halted",
  );
});

test("digest acknowledgment anchor is persisted for future manager checks", () => {
  const snapshot = buildPortfolioDigestSnapshot(
    [
      makeCard({
        session_id: "session-blocking",
        queue_bucket: "new_blocking_now",
        current_blocker: "Review packet requires operator attention.",
        next_action_label: "Resolve intervention packet",
      }),
    ],
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T10:00:00Z" },
  );

  const memory = recordPortfolioDigestTouch(
    createEmptyPortfolioDigestMemory(),
    snapshot,
    { recordedAt: "2026-04-15T10:00:00Z" },
  );

  assert.equal(memory.last_manager_check_at, "2026-04-15T10:00:00Z");
  assert.equal(memory.last_manager_touch_at, "2026-04-15T10:00:00Z");
  assert.equal(memory.last_manager_check_snapshot.recorded_at, "2026-04-15T10:00:00Z");
  assert.equal(memory.last_manager_check_snapshot.sessions[0].session_id, "session-blocking");
  assert.equal(memory.last_manager_touch_snapshot.sessions[0].session_id, "session-blocking");
});

test("manager digest counters and summaries are tied to the last manager check anchor", () => {
  const previousCards = [
    makeCard({
      session_id: "session-blocking",
      queue_bucket: "informational_recent_history",
      checkpoint_count: 1,
      current_cycle: 1,
      what_changed_summary: "No blocker yet.",
      summary_signature: "session-blocking::initial",
    }),
    makeCard({
      session_id: "session-runner",
      queue_bucket: "running_waiting",
      checkpoint_count: 2,
      current_cycle: 2,
      what_changed_summary: "Already progressing.",
      summary_signature: "session-runner::initial",
    }),
  ];
  const previousSnapshot = buildPortfolioDigestSnapshot(previousCards, {
    label: "Open blocking session needing review",
  }, { recordedAt: "2026-04-15T10:00:00Z" });
  const digestMemory = recordPortfolioDigestTouch(
    createEmptyPortfolioDigestMemory(),
    previousSnapshot,
    { recordedAt: "2026-04-15T10:00:00Z" },
  );

  const currentCards = [
    makeCard({
      session_id: "session-blocking",
      queue_bucket: "new_blocking_now",
      checkpoint_count: 2,
      current_cycle: 2,
      current_blocker: "Intervention packet requires operator attention.",
      next_action_label: "Resolve intervention packet",
      what_changed_summary: "1 checkpoint added; review packet created.",
      summary_signature: "session-blocking::blocking",
    }),
    makeCard({
      session_id: "session-runner",
      queue_bucket: "running_waiting",
      checkpoint_count: 4,
      current_cycle: 4,
      what_changed_summary: "2 checkpoints added while the session kept working inside bounds.",
      latest_progress_marker: "checkpoint written",
      summary_signature: "session-runner::advanced",
    }),
    makeCard({
      session_id: "session-resumable",
      queue_bucket: "resumable",
      checkpoint_count: 3,
      current_cycle: 3,
      next_action_label: "Continue until next bounded stop",
      what_changed_summary: "Budget boundary reached; session can resume cleanly.",
      summary_signature: "session-resumable::ready",
    }),
    makeCard({
      session_id: "session-complete",
      queue_bucket: "completed_halted",
      checkpoint_count: 2,
      current_cycle: 2,
      next_action_label: "Review results",
      what_changed_summary: "Bounded run completed and moved into reviewable history.",
      summary_signature: "session-complete::done",
    }),
  ];

  const digest = buildPortfolioManagerDigest(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "Review stays the gate before any lower-priority shell work.",
      targetSessionId: "session-blocking",
      targetCardKey: "session-blocking",
      shortlist: currentCards.slice(0, 2),
    },
    digestMemory,
    { nowIso: "2026-04-15T10:30:00Z" },
  );

  assert.equal(digest.anchor.basis_label, "Since last manager check");
  assert.equal(digest.anchor.recorded_at, "2026-04-15T10:00:00Z");
  assert.equal(digest.counts.sessions_advanced, 2);
  assert.equal(digest.counts.checkpoint_delta, 3);
  assert.equal(digest.counts.new_blockers, 1);
  assert.equal(digest.counts.resumable_since_touch, 1);
  assert.equal(digest.counts.completed_or_halted_since_touch, 1);
  assert.equal(digest.counts.completed_manager_items, 0);
  assert.equal(digest.counts.still_pending_from_before_check, 0);
  assert.equal(digest.counts.overdue_manager_items, 0);
  assert.match(digest.headline, /since the last manager check/i);
  assert.match(digest.meaningfulProgressSummary, /session-runner/i);
  assert.equal(digest.recommendedNextAction.targetSessionId, "session-blocking");
});

test("manager agenda completion tracking keeps current, next, completed, and overdue items distinct without hiding blockers", () => {
  const previousCards = [
    makeCard({
      session_id: "session-reviewed",
      queue_bucket: "new_blocking_now",
      queue_rank: 30,
      current_blocker: "Review packet still needs action.",
      next_action_label: "Resolve intervention packet",
    }),
    makeCard({
      session_id: "session-stale",
      queue_bucket: "acknowledged_unresolved_blocking",
      queue_rank: 20,
      current_blocker: "Previously acknowledged intervention packet.",
      next_action_label: "Resolve intervention packet",
    }),
    makeCard({
      session_id: "session-cleared",
      queue_bucket: "resumable",
      queue_rank: 40,
      next_action_label: "Continue until next bounded stop",
    }),
  ];
  const previousSnapshot = buildPortfolioDigestSnapshot(
    previousCards,
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T10:00:00Z" },
  );
  const digestMemory = recordPortfolioDigestTouch(
    createEmptyPortfolioDigestMemory(),
    previousSnapshot,
    { recordedAt: "2026-04-15T10:00:00Z" },
  );

  const currentCards = [
    makeCard({
      session_id: "session-stale",
      queue_bucket: "stale_escalated_blocking",
      queue_rank: 5,
      current_blocker: "This acknowledged blocker aged into stale escalation.",
      next_action_label: "Resolve intervention packet",
    }),
    makeCard({
      session_id: "session-new",
      queue_bucket: "new_blocking_now",
      queue_rank: 10,
      current_blocker: "Fresh review packet requires operator attention.",
      next_action_label: "Resolve intervention packet",
    }),
    makeCard({
      session_id: "session-reviewed",
      queue_bucket: "new_blocking_now",
      queue_rank: 20,
      current_blocker: "Review packet still needs action.",
      next_action_label: "Resolve intervention packet",
    }),
  ];

  const agenda = buildPortfolioManagerAgenda(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "Review remains the strongest truthful next action.",
      targetSessionId: "session-stale",
      targetCardKey: "session-stale",
    },
    digestMemory,
    { nowIso: "2026-04-15T10:30:00Z" },
  );

  assert.equal(agenda.anchor.basis_label, "Since last manager check");
  assert.equal(agenda.checked_at, "2026-04-15T10:00:00Z");
  assert.equal(agenda.counts.actionable_now, 3);
  assert.equal(agenda.counts.new_since_last_check, 1);
  assert.equal(agenda.counts.reviewed_still_pending, 1);
  assert.equal(agenda.counts.overdue_manager_items, 1);
  assert.equal(agenda.counts.still_pending_from_before_check, 2);
  assert.equal(agenda.counts.completed_since_last_check, 1);
  assert.equal(agenda.counts.cleared_since_last_check, 1);
  assert.equal(agenda.currentItem.session_id, "session-stale");
  assert.equal(agenda.nextItem.session_id, "session-new");
  assert.equal(agenda.justCompletedItem.session_id, "session-cleared");
  assert.match(agenda.currentAgendaSummary, /overdue manager item/i);
  assert.match(agenda.nextAgendaSummary, /new since last check/i);
  assert.match(agenda.completedAgendaSummary, /session-cleared/i);
  assert.match(agenda.overdueAgendaSummary, /overdue manager item/i);
  assert.match(agenda.throughput.headline, /1 item completed/i);
  assert.match(agenda.throughput.detail, /session-new/i);
  assert.deepEqual(
    agenda.completedItems.map((item) => item.session_id),
    ["session-cleared"],
  );
  assert.deepEqual(
    agenda.pendingItems.map((item) => item.session_id),
    ["session-stale", "session-new", "session-reviewed"],
  );
  assert.equal(
    agenda.completedItems[0].completion_outcome_label,
    "Completed since last manager check",
  );
  assert.equal(
    agenda.completedItems[0].resulting_state_label,
    "No longer visible in the current shell queue",
  );
});

test("same-session bounded progress completes one agenda item and surfaces a fresh successor item", () => {
  const previousCards = [
    makeCard({
      session_id: "session-loop",
      queue_bucket: "new_blocking_now",
      queue_rank: 10,
      checkpoint_count: 2,
      current_cycle: 2,
      current_blocker: "Approve the current bounded continuation packet.",
      next_action_label: "Approve bounded continuation",
      summary_signature: "session-loop::before",
    }),
  ];
  const previousSnapshot = buildPortfolioDigestSnapshot(
    previousCards,
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T10:00:00Z" },
  );
  const digestMemory = recordPortfolioDigestTouch(
    createEmptyPortfolioDigestMemory(),
    previousSnapshot,
    { recordedAt: "2026-04-15T10:00:00Z" },
  );

  const currentCards = [
    makeCard({
      session_id: "session-loop",
      queue_bucket: "new_blocking_now",
      queue_rank: 10,
      checkpoint_count: 3,
      current_cycle: 3,
      current_blocker: "Review the next bounded intervention packet.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-loop::after",
    }),
  ];

  const agenda = buildPortfolioManagerAgenda(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "A fresh same-session manager item replaced the prior handled item.",
      targetSessionId: "session-loop",
      targetCardKey: "session-loop",
    },
    digestMemory,
    { nowIso: "2026-04-15T10:30:00Z" },
  );

  assert.equal(agenda.currentItem.session_id, "session-loop");
  assert.equal(agenda.currentItem.agenda_state_key, "new_since_last_check");
  assert.equal(agenda.counts.completed_since_last_check, 1);
  assert.equal(agenda.counts.new_since_last_check, 1);
  assert.equal(agenda.counts.still_pending_from_before_check, 0);
  assert.equal(agenda.completedItems[0].session_id, "session-loop");
  assert.equal(
    agenda.completedItems[0].completion_outcome_label,
    "Completed since last manager check",
  );
});

test("deferred queue return policy and due-ordering stay truthful without overriding blocking truth", () => {
  const currentCards = [
    makeCard({
      session_id: "session-a",
      queue_bucket: "new_blocking_now",
      queue_rank: 10,
      current_blocker: "Resolve the first deferred review packet.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-a::blocking",
    }),
    makeCard({
      session_id: "session-b",
      queue_bucket: "new_blocking_now",
      queue_rank: 20,
      current_blocker: "Resolve the second deferred review packet.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-b::blocking",
    }),
    makeCard({
      session_id: "session-c",
      queue_bucket: "new_blocking_now",
      queue_rank: 5,
      current_blocker: "Handle the live current blocking session.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-c::blocking",
    }),
  ];
  const previousSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T10:00:00Z" },
  );
  const digestMemory = recordPortfolioDigestTouch(
    createEmptyPortfolioDigestMemory(),
    previousSnapshot,
    { recordedAt: "2026-04-15T10:00:00Z" },
  );

  const deferredA = deferPortfolioManagerItem(digestMemory, currentCards[0], {
    deferredAt: "2026-04-15T10:05:00Z",
  });
  assert.equal(Boolean(deferredA.changed), true);
  const deferredB = deferPortfolioManagerItem(deferredA.memory, currentCards[1], {
    deferredAt: "2026-04-15T10:06:00Z",
    deferBasisKey: "until_reopen",
    deferBasisLabel: "Deferred until reopened",
  });
  assert.equal(Boolean(deferredB.changed), true);

  const deferredAgenda = buildPortfolioManagerAgenda(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "Defer two items locally and keep the live current session actionable now.",
      targetSessionId: "session-c",
      targetCardKey: "session-c",
    },
    deferredB.memory,
    { nowIso: "2026-04-15T10:10:00Z" },
  );

  assert.equal(deferredAgenda.currentItem.session_id, "session-c");
  assert.deepEqual(
    deferredAgenda.deferredItems.map((item) => item.session_id),
    ["session-a", "session-b"],
  );
  assert.equal(
    deferredAgenda.itemStateBySessionId["session-a"].key,
    "deferred_until_next_manager_check",
  );
  assert.equal(
    deferredAgenda.itemStateBySessionId["session-b"].key,
    "deferred_until_reopen",
  );
  assert.equal(deferredAgenda.counts.deferred_items, 2);
  assert.equal(deferredAgenda.counts.deferred_since_last_check, 2);
  assert.equal(
    classifyOperatorQueueGroup(currentCards[0]),
    "pending_review_intervention",
  );

  const nextCheckSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    {
      label: "Open blocking session needing review",
    },
    { recordedAt: "2026-04-15T10:30:00Z" },
  );
  const dueMemory = recordPortfolioDigestTouch(deferredB.memory, nextCheckSnapshot, {
    recordedAt: "2026-04-15T10:30:00Z",
  });
  const dueAgenda = buildPortfolioManagerAgenda(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "One deferred item is now due because the next manager check was recorded.",
      targetSessionId: "session-a",
      targetCardKey: "session-a",
    },
    dueMemory,
    { nowIso: "2026-04-15T10:31:00Z" },
  );
  assert.equal(dueAgenda.currentItem.session_id, "session-a");
  assert.equal(dueAgenda.currentItem.agenda_state_key, "due_return_now");
  assert.equal(dueAgenda.dueItems[0].session_id, "session-a");
  assert.equal(dueAgenda.deferredItems[0].session_id, "session-b");
  assert.equal(dueAgenda.counts.due_now, 1);
  assert.equal(dueAgenda.counts.deferred_items, 1);
  assert.equal(dueAgenda.counts.due_returned_since_last_check, 1);

  const reopened = reopenPortfolioManagerItem(dueMemory, currentCards[1], {
    reopenedAt: "2026-04-15T10:35:00Z",
  });
  assert.equal(Boolean(reopened.changed), true);

  const reopenedAgenda = buildPortfolioManagerAgenda(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "The second deferred item returned to the active agenda manually.",
      targetSessionId: "session-a",
      targetCardKey: "session-a",
    },
    reopened.memory,
    { nowIso: "2026-04-15T10:36:00Z" },
  );
  const reopenedDigest = buildPortfolioManagerDigest(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "The second deferred item returned to the active agenda manually.",
      targetSessionId: "session-a",
      targetCardKey: "session-a",
    },
    reopened.memory,
    { nowIso: "2026-04-15T10:36:00Z" },
  );

  assert.equal(reopenedAgenda.currentItem.session_id, "session-a");
  assert.equal(reopenedAgenda.currentItem.agenda_state_key, "due_return_now");
  assert.equal(reopenedAgenda.nextItem.session_id, "session-b");
  assert.equal(reopenedAgenda.nextItem.agenda_state_key, "reopened_after_defer");
  assert.equal(reopenedAgenda.counts.deferred_items, 0);
  assert.equal(reopenedAgenda.counts.due_returned_since_last_check, 1);
  assert.equal(reopenedAgenda.counts.reopened_since_last_check, 1);
  assert.equal(reopenedAgenda.counts.reopened_items, 1);
  assert.equal(reopenedDigest.counts.deferred_since_last_check, 0);
  assert.equal(reopenedDigest.counts.due_returned_since_last_check, 1);
  assert.equal(reopenedDigest.counts.reopened_since_last_check, 1);

  const laterSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    {
      label: "Open blocking session needing review",
    },
    { recordedAt: "2026-04-15T11:00:00Z" },
  );
  const overdueMemory = recordPortfolioDigestTouch(reopened.memory, laterSnapshot, {
    recordedAt: "2026-04-15T11:00:00Z",
  });
  const overdueAgenda = buildPortfolioManagerAgenda(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "Returned deferred work that stays unresolved should age into overdue-after-return state.",
      targetSessionId: "session-a",
      targetCardKey: "session-a",
    },
    overdueMemory,
    { nowIso: "2026-04-15T11:01:00Z" },
  );

  assert.equal(overdueAgenda.currentItem.session_id, "session-a");
  assert.equal(overdueAgenda.currentItem.agenda_state_key, "overdue_after_return");
  assert.equal(overdueAgenda.nextItem.session_id, "session-b");
  assert.equal(overdueAgenda.nextItem.agenda_state_key, "overdue_after_return");
  assert.equal(overdueAgenda.counts.overdue_after_return, 2);
});

test("deferred workload digest and return-basis throughput stay truthful across defer, due return, reopen, and overdue states", () => {
  const currentCards = [
    makeCard({
      session_id: "session-a",
      queue_bucket: "new_blocking_now",
      queue_rank: 10,
      current_blocker: "Resolve the first deferred review packet.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-a::blocking",
    }),
    makeCard({
      session_id: "session-b",
      queue_bucket: "new_blocking_now",
      queue_rank: 20,
      current_blocker: "Resolve the second deferred review packet.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-b::blocking",
    }),
    makeCard({
      session_id: "session-c",
      queue_bucket: "new_blocking_now",
      queue_rank: 5,
      current_blocker: "Handle the live current blocking session.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-c::blocking",
    }),
  ];
  const previousSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T10:00:00Z" },
  );
  const digestMemory = recordPortfolioDigestTouch(
    createEmptyPortfolioDigestMemory(),
    previousSnapshot,
    { recordedAt: "2026-04-15T10:00:00Z" },
  );

  const deferredA = deferPortfolioManagerItem(digestMemory, currentCards[0], {
    deferredAt: "2026-04-15T10:05:00Z",
  });
  const deferredB = deferPortfolioManagerItem(deferredA.memory, currentCards[1], {
    deferredAt: "2026-04-15T10:06:00Z",
    deferBasisKey: "until_reopen",
    deferBasisLabel: "Deferred until reopened",
  });

  const parkedDigest = buildPortfolioDeferredWorkloadDigest(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "Two deferred items are parked while the live session stays current.",
      targetSessionId: "session-c",
      targetCardKey: "session-c",
    },
    deferredB.memory,
    { nowIso: "2026-04-15T10:10:00Z" },
  );
  assert.equal(parkedDigest.counts.total_deferred_items, 2);
  assert.equal(parkedDigest.counts.deferred_not_yet_due, 2);
  assert.equal(parkedDigest.counts.due_now, 0);
  assert.equal(parkedDigest.counts.reopened_manually, 0);
  assert.equal(parkedDigest.counts.deferred_since_last_check, 2);
  assert.equal(parkedDigest.counts.return_basis_next_manager_check, 1);
  assert.equal(parkedDigest.counts.return_basis_until_reopen, 1);
  assert.equal(parkedDigest.pressureBand.key, "low");
  assert.match(parkedDigest.pressureBand.detail, /low/i);
  assert.match(parkedDigest.responsePolicy.primary.label, /continue current work/i);

  const nextCheckSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T10:30:00Z" },
  );
  const dueMemory = recordPortfolioDigestTouch(deferredB.memory, nextCheckSnapshot, {
    recordedAt: "2026-04-15T10:30:00Z",
  });
  const dueDigest = buildPortfolioDeferredWorkloadDigest(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "One deferred item became due at the latest manager check.",
      targetSessionId: "session-a",
      targetCardKey: "session-a",
    },
    dueMemory,
    { nowIso: "2026-04-15T10:31:00Z" },
  );
  assert.equal(dueDigest.counts.total_deferred_items, 2);
  assert.equal(dueDigest.counts.deferred_not_yet_due, 1);
  assert.equal(dueDigest.counts.due_now, 1);
  assert.equal(dueDigest.counts.due_returned_since_last_check, 1);
  assert.equal(dueDigest.counts.reopened_since_last_check, 0);
  assert.equal(dueDigest.counts.return_basis_next_manager_check, 1);
  assert.equal(dueDigest.counts.return_basis_until_reopen, 1);
  assert.equal(dueDigest.pressureBand.key, "rising");
  assert.match(dueDigest.responsePolicy.primary.label, /clear due-now items first/i);
  assert.match(dueDigest.detail, /became due/i);

  const reopened = reopenPortfolioManagerItem(dueMemory, currentCards[1], {
    reopenedAt: "2026-04-15T10:35:00Z",
  });
  const reopenedDigest = buildPortfolioDeferredWorkloadDigest(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "One deferred item is due now and another returned by manual reopen.",
      targetSessionId: "session-a",
      targetCardKey: "session-a",
    },
    reopened.memory,
    { nowIso: "2026-04-15T10:36:00Z" },
  );
  assert.equal(reopenedDigest.counts.total_deferred_items, 2);
  assert.equal(reopenedDigest.counts.deferred_not_yet_due, 0);
  assert.equal(reopenedDigest.counts.due_now, 1);
  assert.equal(reopenedDigest.counts.reopened_manually, 1);
  assert.equal(reopenedDigest.counts.returned_since_last_check, 2);
  assert.equal(reopenedDigest.counts.reopened_since_last_check, 1);
  assert.equal(reopenedDigest.counts.return_basis_next_manager_check, 1);
  assert.equal(reopenedDigest.counts.return_basis_until_reopen, 1);
  assert.equal(reopenedDigest.pressureBand.key, "rising");
  assert.match(reopenedDigest.responsePolicy.detail, /manual reopen/i);
  assert.match(reopenedDigest.detail, /manual reopen/i);

  const laterSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T11:00:00Z" },
  );
  const overdueMemory = recordPortfolioDigestTouch(reopened.memory, laterSnapshot, {
    recordedAt: "2026-04-15T11:00:00Z",
  });
  const overdueDigest = buildPortfolioDeferredWorkloadDigest(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "Returned deferred work aged into overdue-after-return at the next manager check.",
      targetSessionId: "session-a",
      targetCardKey: "session-a",
    },
    overdueMemory,
    { nowIso: "2026-04-15T11:01:00Z" },
  );
  assert.equal(overdueDigest.counts.total_deferred_items, 2);
  assert.equal(overdueDigest.counts.due_now, 0);
  assert.equal(overdueDigest.counts.overdue_after_return, 2);
  assert.equal(overdueDigest.counts.overdue_after_return_since_last_check, 2);
  assert.equal(overdueDigest.counts.return_basis_next_manager_check, 1);
  assert.equal(overdueDigest.counts.return_basis_until_reopen, 1);
  assert.equal(overdueDigest.pressureBand.key, "high");
  assert.match(overdueDigest.responsePolicy.primary.label, /overdue-after-return/i);
  assert.match(overdueDigest.detail, /overdue-after-return/i);
});

test("response outcome tracking marks deferred pressure as improved after the suggested response reduces due-now work", () => {
  const currentCards = [
    makeCard({
      session_id: "session-a",
      queue_bucket: "new_blocking_now",
      queue_rank: 10,
      current_blocker: "Resolve the first deferred review packet.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-a::blocking",
    }),
    makeCard({
      session_id: "session-b",
      queue_bucket: "new_blocking_now",
      queue_rank: 20,
      current_blocker: "Resolve the second deferred review packet.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-b::blocking",
    }),
    makeCard({
      session_id: "session-c",
      queue_bucket: "new_blocking_now",
      queue_rank: 5,
      current_blocker: "Handle the live current blocking session.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-c::blocking",
    }),
  ];
  const baselineSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T10:00:00Z" },
  );
  const baselineMemory = recordPortfolioDigestTouch(
    createEmptyPortfolioDigestMemory(),
    baselineSnapshot,
    { recordedAt: "2026-04-15T10:00:00Z" },
  );
  const deferredA = deferPortfolioManagerItem(baselineMemory, currentCards[0], {
    deferredAt: "2026-04-15T10:05:00Z",
  });
  const deferredB = deferPortfolioManagerItem(deferredA.memory, currentCards[1], {
    deferredAt: "2026-04-15T10:06:00Z",
    deferBasisKey: "until_reopen",
    deferBasisLabel: "Deferred until reopened",
  });
  const nextCheckSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T10:30:00Z" },
  );
  const dueMemory = recordPortfolioDigestTouch(deferredB.memory, nextCheckSnapshot, {
    recordedAt: "2026-04-15T10:30:00Z",
  });
  const dueDigest = buildPortfolioDeferredWorkloadDigest(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "One deferred item became due at the latest manager check.",
      targetSessionId: "session-a",
      targetCardKey: "session-a",
    },
    dueMemory,
    { nowIso: "2026-04-15T10:31:00Z" },
  );
  const anchoredMemory = recordDeferredResponseAnchor(dueMemory, dueDigest, {
    recordedAt: "2026-04-15T10:31:30Z",
    source: "shell_action",
    targetSessionId: "session-a",
    actionLabel: "Resolve intervention packet",
  });

  const afterActionCards = [
    makeCard({
      session_id: "session-a",
      queue_bucket: "completed_halted",
      queue_rank: 90,
      lifecycle_section: "completed",
      lifecycle_state: "completed",
      current_blocker: "",
      next_action_label: "",
      next_action_detail: "",
      summary_signature: "session-a::recent",
    }),
    currentCards[1],
    currentCards[2],
  ];
  const improvedDigest = buildPortfolioDeferredWorkloadDigest(
    afterActionCards,
    {
      label: "Resume any deferred manager item still requiring review",
      detail: "The due-now item was handled and pressure fell back to parked backlog only.",
      targetSessionId: "session-c",
      targetCardKey: "session-c",
    },
    anchoredMemory,
    { nowIso: "2026-04-15T10:40:00Z" },
  );

  assert.equal(improvedDigest.pressureBand.key, "rising");
  assert.equal(improvedDigest.responseOutcome.key, "improved");
  assert.equal(improvedDigest.responseOutcome.basisKey, "since_last_suggested_response");
  assert.equal(improvedDigest.responseOutcome.previousBandKey, "rising");
  assert.equal(improvedDigest.responseOutcome.currentBandKey, "rising");
  assert.match(improvedDigest.responseOutcome.detail, /due-now/i);
  assert.match(improvedDigest.responseOutcome.currentResponseLabel, /manual reopen/i);
});

test("response outcome tracking marks deferred pressure as worsened when a due item appears after a low-pressure response anchor", () => {
  const currentCards = [
    makeCard({
      session_id: "session-a",
      queue_bucket: "new_blocking_now",
      queue_rank: 10,
      current_blocker: "Resolve the first deferred review packet.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-a::blocking",
    }),
    makeCard({
      session_id: "session-b",
      queue_bucket: "new_blocking_now",
      queue_rank: 20,
      current_blocker: "Resolve the second deferred review packet.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-b::blocking",
    }),
    makeCard({
      session_id: "session-c",
      queue_bucket: "new_blocking_now",
      queue_rank: 5,
      current_blocker: "Handle the live current blocking session.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-c::blocking",
    }),
  ];
  const baselineSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T10:00:00Z" },
  );
  const baselineMemory = recordPortfolioDigestTouch(
    createEmptyPortfolioDigestMemory(),
    baselineSnapshot,
    { recordedAt: "2026-04-15T10:00:00Z" },
  );
  const deferredA = deferPortfolioManagerItem(baselineMemory, currentCards[0], {
    deferredAt: "2026-04-15T10:05:00Z",
  });
  const deferredB = deferPortfolioManagerItem(deferredA.memory, currentCards[1], {
    deferredAt: "2026-04-15T10:06:00Z",
    deferBasisKey: "until_reopen",
    deferBasisLabel: "Deferred until reopened",
  });
  const parkedDigest = buildPortfolioDeferredWorkloadDigest(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "Two deferred items are parked while the live session stays current.",
      targetSessionId: "session-c",
      targetCardKey: "session-c",
    },
    deferredB.memory,
    { nowIso: "2026-04-15T10:10:00Z" },
  );
  const anchoredMemory = recordDeferredResponseAnchor(deferredB.memory, parkedDigest, {
    recordedAt: "2026-04-15T10:11:00Z",
    source: "shell_action",
    targetSessionId: "session-c",
    actionLabel: "Resolve intervention packet",
  });
  const nextCheckSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    { label: "Open blocking session needing review" },
    {
      recordedAt: "2026-04-15T10:30:00Z",
      deferredState: buildDeferredResponseAnchorState(parkedDigest, {
        recordedAt: "2026-04-15T10:30:00Z",
        source: "manager_check",
      }),
    },
  );
  const dueMemory = recordPortfolioDigestTouch(anchoredMemory, nextCheckSnapshot, {
    recordedAt: "2026-04-15T10:30:00Z",
  });
  const worsenedDigest = buildPortfolioDeferredWorkloadDigest(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "One deferred item became due at the latest manager check.",
      targetSessionId: "session-a",
      targetCardKey: "session-a",
    },
    dueMemory,
    { nowIso: "2026-04-15T10:31:00Z" },
  );

  assert.equal(worsenedDigest.responseOutcome.key, "worsened");
  assert.equal(worsenedDigest.responseOutcome.basisKey, "since_last_manager_check");
  assert.equal(worsenedDigest.responseOutcome.previousBandKey, "low");
  assert.equal(worsenedDigest.responseOutcome.currentBandKey, "rising");
  assert.match(worsenedDigest.responseOutcome.detail, /pressure band moved/i);
  assert.match(worsenedDigest.responsePolicy.primary.label, /clear due-now items first/i);
});

test("response outcome tracking marks deferred pressure as stable when overdue pressure persists across the last suggested response", () => {
  const currentCards = [
    makeCard({
      session_id: "session-a",
      queue_bucket: "new_blocking_now",
      queue_rank: 10,
      current_blocker: "Resolve the first deferred review packet.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-a::blocking",
    }),
    makeCard({
      session_id: "session-b",
      queue_bucket: "new_blocking_now",
      queue_rank: 20,
      current_blocker: "Resolve the second deferred review packet.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-b::blocking",
    }),
    makeCard({
      session_id: "session-c",
      queue_bucket: "new_blocking_now",
      queue_rank: 5,
      current_blocker: "Handle the live current blocking session.",
      next_action_label: "Resolve intervention packet",
      summary_signature: "session-c::blocking",
    }),
  ];
  const baselineSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T10:00:00Z" },
  );
  const baselineMemory = recordPortfolioDigestTouch(
    createEmptyPortfolioDigestMemory(),
    baselineSnapshot,
    { recordedAt: "2026-04-15T10:00:00Z" },
  );
  const deferredA = deferPortfolioManagerItem(baselineMemory, currentCards[0], {
    deferredAt: "2026-04-15T10:05:00Z",
  });
  const deferredB = deferPortfolioManagerItem(deferredA.memory, currentCards[1], {
    deferredAt: "2026-04-15T10:06:00Z",
    deferBasisKey: "until_reopen",
    deferBasisLabel: "Deferred until reopened",
  });
  const nextCheckSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T10:30:00Z" },
  );
  const dueMemory = recordPortfolioDigestTouch(deferredB.memory, nextCheckSnapshot, {
    recordedAt: "2026-04-15T10:30:00Z",
  });
  const reopened = reopenPortfolioManagerItem(dueMemory, currentCards[1], {
    reopenedAt: "2026-04-15T10:35:00Z",
  });
  const laterSnapshot = buildPortfolioDigestSnapshot(
    currentCards,
    { label: "Open blocking session needing review" },
    { recordedAt: "2026-04-15T11:00:00Z" },
  );
  const overdueMemory = recordPortfolioDigestTouch(reopened.memory, laterSnapshot, {
    recordedAt: "2026-04-15T11:00:00Z",
  });
  const overdueDigest = buildPortfolioDeferredWorkloadDigest(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "Returned deferred work aged into overdue-after-return at the next manager check.",
      targetSessionId: "session-a",
      targetCardKey: "session-a",
    },
    overdueMemory,
    { nowIso: "2026-04-15T11:01:00Z" },
  );
  const anchoredMemory = recordDeferredResponseAnchor(overdueMemory, overdueDigest, {
    recordedAt: "2026-04-15T11:02:00Z",
    source: "shell_action",
    targetSessionId: "session-a",
    actionLabel: "Resolve intervention packet",
  });
  const stableDigest = buildPortfolioDeferredWorkloadDigest(
    currentCards,
    {
      label: "Open blocking session needing review",
      detail: "No overdue deferred work was cleared after the last suggested response.",
      targetSessionId: "session-a",
      targetCardKey: "session-a",
    },
    anchoredMemory,
    { nowIso: "2026-04-15T11:10:00Z" },
  );

  assert.equal(stableDigest.responseOutcome.key, "stable");
  assert.equal(stableDigest.responseOutcome.previousBandKey, "high");
  assert.equal(stableDigest.responseOutcome.currentBandKey, "high");
  assert.match(stableDigest.responseOutcome.detail, /remain|still/i);
  assert.match(stableDigest.responsePolicy.primary.label, /overdue-after-return/i);
});

test("operator queue keeps current blockers visible while preserving lineage fields", () => {
  const blockingCard = makeCard({
    session_id: "session-blocking",
    queue_bucket: "new_blocking_now",
    checkpoint_id: "session-blocking::checkpoint::0003",
    current_blocker: "Review packet requires operator attention.",
    next_action_label: "Resolve intervention packet",
  });
  const resumableCard = makeCard({
    session_id: "session-resumable",
    queue_bucket: "resumable",
    checkpoint_id: "session-resumable::checkpoint::0004",
    next_action_label: "Continue until next bounded stop",
  });
  const informationalCard = makeCard({
    session_id: "session-info",
    queue_bucket: "informational_recent_history",
    lifecycle_section: "recent",
  });
  const completedCard = makeCard({
    session_id: "session-complete",
    queue_bucket: "completed_halted",
    lifecycle_section: "recent",
  });
  const archivedCard = makeCard({
    session_id: "session-archived",
    queue_bucket: "completed_halted",
    lifecycle_section: "archived",
    archived: true,
  });

  const queue = buildPortfolioOperatorQueue(
    [informationalCard, completedCard, archivedCard, resumableCard, blockingCard],
    {
      label: "Open blocking session needing review",
      detail: "Review remains the gate.",
      targetSessionId: "session-blocking",
      targetCardKey: "session-blocking",
      shortlist: [blockingCard, resumableCard],
    },
  );

  assert.equal(queue.counts.actionable_now, 2);
  assert.equal(queue.counts.safe_to_ignore, 3);
  assert.equal(queue.dominantAction.targetSessionId, "session-blocking");
  assert.deepEqual(
    queue.sections.map((section) => section.key),
    ["pending_review_intervention", "resumable", "completed_halted", "archived_informational"],
  );
  assert.equal(queue.sections[0].cards[0].session_id, "session-blocking");
  assert.equal(queue.sections[0].cards[0].checkpoint_id, "session-blocking::checkpoint::0003");
  assert.ok(
    !queue.sections[3].cards.some((card) => card.session_id === "session-blocking"),
    "current blockers must not be hidden in archived/informational buckets",
  );
});
