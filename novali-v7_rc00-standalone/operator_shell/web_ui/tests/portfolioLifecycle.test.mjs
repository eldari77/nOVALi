import test from "node:test";
import assert from "node:assert/strict";

import {
  buildHandoffMemoryEntry,
  createEmptyAttentionMemory,
  upsertHandoffMemory,
} from "../src/lib/attentionMemory.js";
import { buildSessionPortfolio } from "../src/lib/sessionPortfolio.js";
import {
  applyPortfolioLifecycleAction,
  buildManagedSessionPortfolio,
  createEmptyPortfolioLifecycleMemory,
  isActionablePortfolioCard,
} from "../src/lib/portfolioLifecycle.js";

function buildPayload(overrides = {}) {
  const sessionId = overrides.session_id || "operator_session::lifecycle";
  const checkpointId = overrides.checkpoint_id || `${sessionId}::checkpoint::0002`;
  return {
    longRunState: {
      long_run: {
        session_id: sessionId,
        lifecycle_state: overrides.lifecycle_state || "paused_for_intervention",
        latest_checkpoint_id: checkpointId,
        checkpoint_count: overrides.checkpoint_count ?? 2,
        current_cycle: overrides.current_cycle ?? 2,
        max_cycles: overrides.max_cycles ?? 4,
        last_checkpoint_at: overrides.checkpoint_at || "2026-04-15T12:00:00Z",
        halt_reason: overrides.stop_reason || "intervention_required",
      },
      operator_guidance: {
        session_handle: overrides.session_handle || sessionId.slice(-6),
        state_family: overrides.state_family || "attention_required",
        headroom_summary:
          overrides.policy_headroom_summary || "2 cycles remain before the bounded policy stops again.",
        settings_summary: overrides.settings_summary || "until bounded stop · total-cycle cap 4",
        next_stop_boundary_label: overrides.next_stop || "Intervention review",
        next_stop_boundary_summary:
          overrides.next_stop_summary || "Another explicit operator review can stop the same session again.",
      },
    },
    attentionSignal: {
      severity: overrides.severity || "blocking",
      packet_id: overrides.packet_id || "packet-0002",
      blocking_count: overrides.blocking_count ?? 1,
      informational_count: overrides.informational_count ?? 0,
    },
    campaignHandoff: {
      label: "Campaign handoff summary",
      session_id: sessionId,
      session_handle: overrides.session_handle || sessionId.slice(-6),
      lifecycle_state: overrides.lifecycle_state || "paused_for_intervention",
      state_label: overrides.state_label || "Paused for intervention",
      last_checkpoint_id: checkpointId,
      last_checkpoint_at: overrides.checkpoint_at || "2026-04-15T12:00:00Z",
      current_cycle: overrides.current_cycle ?? 2,
      max_cycles: overrides.max_cycles ?? 4,
      checkpoint_count: overrides.checkpoint_count ?? 2,
      what_changed_summary:
        overrides.what_changed_summary || "1 checkpoint added; 1 cycle completed; review packet created.",
      current_blocker: overrides.current_blocker || "Review packet requires operator attention.",
      recommended_next_action_label: overrides.next_action || "Resolve intervention packet",
      recommended_next_action_detail:
        overrides.next_action_detail || "Review the bounded packet and then continue the same session.",
      next_stop_boundary_label: overrides.next_stop || "Intervention review",
      next_stop_boundary_summary:
        overrides.next_stop_summary || "Another explicit operator review can stop the same session again.",
      attention_blocking_count: overrides.blocking_count ?? 1,
      attention_informational_count: overrides.informational_count ?? 0,
      policy_headroom_summary:
        overrides.policy_headroom_summary || "2 cycles remain before the bounded policy stops again.",
      latest_progress_marker: overrides.latest_progress_marker || "checkpoint written",
      resume_ready_after_next_action: overrides.resume_ready_after_next_action ?? true,
    },
    deltaSinceLastResume: {
      summary: overrides.delta_summary || "1 checkpoint added; 1 cycle completed.",
    },
  };
}

function buildPortfolioCards() {
  const currentBlocking = buildHandoffMemoryEntry(
    buildPayload({
      session_id: "operator_session::blocking",
      checkpoint_id: "operator_session::blocking::checkpoint::0003",
    }),
  );
  const completedHistory = buildHandoffMemoryEntry(
    buildPayload({
      session_id: "operator_session::completed",
      checkpoint_id: "operator_session::completed::checkpoint::0004",
      lifecycle_state: "halted",
      state_label: "Halted",
      stop_reason: "budget_exhausted",
      next_action: "Review results",
      next_action_detail: "Inspect the completed bounded session summary.",
      current_blocker: "Bounded run exhausted the total cycle budget.",
      current_cycle: 4,
      max_cycles: 4,
      policy_headroom_summary: "0 total cycle(s) remain.",
      blocking_count: 1,
    }),
  );
  const informationalRecent = buildHandoffMemoryEntry(
    buildPayload({
      session_id: "operator_session::recent",
      checkpoint_id: "operator_session::recent::checkpoint::0005",
      severity: "informational",
      blocking_count: 0,
      informational_count: 1,
      lifecycle_state: "waiting_for_next_invocation",
      state_label: "Waiting for next invocation",
      stop_reason: "budget_boundary_reached",
      current_blocker: "Informational session update only.",
      next_action: "Review results",
      next_stop: "Budget boundary",
      resume_ready_after_next_action: false,
    }),
  );

  let memory = createEmptyAttentionMemory();
  memory = upsertHandoffMemory(memory, completedHistory).memory;
  memory = upsertHandoffMemory(memory, informationalRecent).memory;
  memory = upsertHandoffMemory(memory, currentBlocking).memory;

  return buildSessionPortfolio(memory, {
    currentSessionId: "operator_session::blocking",
  }).cards;
}

test("pin and unpin do not change backend-derived blocking bucket truth", () => {
  const cards = buildPortfolioCards();
  const blockingCard = cards.find((card) => card.session_id === "operator_session::blocking");
  assert.equal(isActionablePortfolioCard(blockingCard), true);

  let lifecycleMemory = createEmptyPortfolioLifecycleMemory();
  lifecycleMemory = applyPortfolioLifecycleAction(lifecycleMemory, blockingCard, "pin").memory;
  let managed = buildManagedSessionPortfolio(cards, null, lifecycleMemory);
  let managedBlocking = managed.all_visible_cards.find(
    (card) => card.session_id === "operator_session::blocking",
  );
  assert.equal(managedBlocking.pinned, true);
  assert.equal(managedBlocking.queue_bucket, "new_blocking_now");
  assert.equal(managedBlocking.lifecycle_section, "active");

  lifecycleMemory = applyPortfolioLifecycleAction(lifecycleMemory, blockingCard, "unpin").memory;
  managed = buildManagedSessionPortfolio(cards, null, lifecycleMemory);
  managedBlocking = managed.all_visible_cards.find(
    (card) => card.session_id === "operator_session::blocking",
  );
  assert.equal(managedBlocking.pinned, false);
  assert.equal(managedBlocking.queue_bucket, "new_blocking_now");
});

test("archiving is blocked for actionable sessions but allowed for completed history", () => {
  const cards = buildPortfolioCards();
  const blockingCard = cards.find((card) => card.session_id === "operator_session::blocking");
  const completedCard = cards.find((card) => card.session_id === "operator_session::completed");

  let lifecycleMemory = createEmptyPortfolioLifecycleMemory();
  const blockedArchive = applyPortfolioLifecycleAction(lifecycleMemory, blockingCard, "archive");
  assert.equal(blockedArchive.changed, false);
  assert.match(blockedArchive.blocked_reason, /discoverable/i);

  lifecycleMemory = applyPortfolioLifecycleAction(lifecycleMemory, completedCard, "archive").memory;
  const managed = buildManagedSessionPortfolio(cards, null, lifecycleMemory);
  const archivedCard = managed.all_visible_cards.find(
    (card) => card.session_id === "operator_session::completed",
  );
  assert.equal(archivedCard.archived, true);
  assert.equal(archivedCard.lifecycle_section, "archived");
  assert.equal(archivedCard.session_id, "operator_session::completed");
  assert.equal(archivedCard.checkpoint_id, "operator_session::completed::checkpoint::0004");
});

test("queue recommendation stays focused on actionable sessions after lifecycle actions", () => {
  const cards = buildPortfolioCards();
  const completedCard = cards.find((card) => card.session_id === "operator_session::completed");
  const informationalCard = cards.find((card) => card.session_id === "operator_session::recent");

  let lifecycleMemory = createEmptyPortfolioLifecycleMemory();
  lifecycleMemory = applyPortfolioLifecycleAction(lifecycleMemory, completedCard, "pin").memory;
  lifecycleMemory = applyPortfolioLifecycleAction(lifecycleMemory, informationalCard, "archive").memory;

  const managed = buildManagedSessionPortfolio(cards, null, lifecycleMemory);
  assert.equal(managed.recommendation.target_session_id, "operator_session::blocking");
  assert.equal(managed.sections.find((section) => section.key === "active")?.cards[0]?.session_id, "operator_session::blocking");
  assert.equal(managed.sections.find((section) => section.key === "pinned")?.cards[0]?.session_id, "operator_session::completed");
  assert.equal(managed.sections.find((section) => section.key === "archived")?.cards[0]?.session_id, "operator_session::recent");
});

test("restoring an archived session preserves lineage and returns it to non-archived history", () => {
  const cards = buildPortfolioCards();
  const completedCard = cards.find((card) => card.session_id === "operator_session::completed");

  let lifecycleMemory = createEmptyPortfolioLifecycleMemory();
  lifecycleMemory = applyPortfolioLifecycleAction(lifecycleMemory, completedCard, "archive").memory;
  lifecycleMemory = applyPortfolioLifecycleAction(lifecycleMemory, completedCard, "restore").memory;

  const managed = buildManagedSessionPortfolio(cards, null, lifecycleMemory);
  const restoredCard = managed.all_visible_cards.find(
    (card) => card.session_id === "operator_session::completed",
  );
  assert.equal(restoredCard.archived, false);
  assert.notEqual(restoredCard.lifecycle_section, "archived");
  assert.equal(restoredCard.entry_key, completedCard.entry_key);
});
