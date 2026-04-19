import test from "node:test";
import assert from "node:assert/strict";

import {
  buildHandoffMemoryEntry,
  createEmptyAttentionMemory,
  markHandoffEntryState,
  upsertHandoffMemory,
} from "../src/lib/attentionMemory.js";
import {
  buildPortfolioNavigationTarget,
  buildSessionPortfolio,
  classifyPortfolioSessionBucket,
} from "../src/lib/sessionPortfolio.js";

function buildPayload(overrides = {}) {
  const sessionId = overrides.session_id || "operator_session::portfolio";
  const checkpointId = overrides.checkpoint_id || `${sessionId}::checkpoint::0002`;
  return {
    longRunState: {
      long_run: {
        session_id: sessionId,
        lifecycle_state: overrides.lifecycle_state || "paused_for_intervention",
        latest_checkpoint_id: checkpointId,
        checkpoint_count: overrides.checkpoint_count ?? 2,
        current_cycle: overrides.current_cycle ?? 2,
        max_cycles: overrides.max_cycles ?? 5,
        last_checkpoint_at: overrides.checkpoint_at || "2026-04-14T12:00:00Z",
        halt_reason: overrides.stop_reason || "intervention_required",
      },
      operator_guidance: {
        session_handle: overrides.session_handle || sessionId.slice(-6),
        state_family: overrides.state_family || "attention_required",
        headroom_summary:
          overrides.policy_headroom_summary || "3 cycles remaining before the bounded policy stops again.",
        settings_summary: overrides.settings_summary || "until bounded stop · total-cycle cap 5",
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
      last_checkpoint_at: overrides.checkpoint_at || "2026-04-14T12:00:00Z",
      current_cycle: overrides.current_cycle ?? 2,
      max_cycles: overrides.max_cycles ?? 5,
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
        overrides.policy_headroom_summary || "3 cycles remaining before the bounded policy stops again.",
      latest_progress_marker: overrides.latest_progress_marker || "checkpoint written",
      resume_ready_after_next_action: overrides.resume_ready_after_next_action ?? true,
    },
    deltaSinceLastResume: {
      summary: overrides.delta_summary || "1 checkpoint added; 1 cycle completed.",
    },
  };
}

test("portfolio queue ranks new blocking current session ahead of resumable recent history", () => {
  const blockingEntry = buildHandoffMemoryEntry(
    buildPayload({
      session_id: "operator_session::blocking",
      checkpoint_id: "operator_session::blocking::checkpoint::0003",
      current_cycle: 3,
      checkpoint_count: 3,
    }),
  );
  const resumableEntry = buildHandoffMemoryEntry(
    buildPayload({
      session_id: "operator_session::resumable",
      checkpoint_id: "operator_session::resumable::checkpoint::0004",
      severity: "clear",
      blocking_count: 0,
      informational_count: 0,
      lifecycle_state: "waiting_for_next_invocation",
      state_label: "Waiting for next invocation",
      stop_reason: "budget_boundary_reached",
      current_blocker: "No current blocker remains.",
      next_action: "Continue until next bounded stop",
      next_action_detail: "Resume the same bounded session from the latest checkpoint.",
      next_stop: "Budget boundary",
      checkpoint_count: 4,
      current_cycle: 4,
      resume_ready_after_next_action: true,
    }),
  );

  let memory = createEmptyAttentionMemory();
  memory = upsertHandoffMemory(memory, resumableEntry).memory;
  memory = upsertHandoffMemory(memory, blockingEntry).memory;

  const portfolio = buildSessionPortfolio(memory, {
    currentSessionId: "operator_session::blocking",
  });
  assert.equal(portfolio.cards.length, 2);
  assert.equal(portfolio.cards[0].session_id, "operator_session::blocking");
  assert.equal(portfolio.cards[0].queue_bucket, "new_blocking_now");
  assert.equal(portfolio.cards[0].checkpoint_id, "operator_session::blocking::checkpoint::0003");
  assert.equal(portfolio.cards[1].session_id, "operator_session::resumable");
  assert.equal(portfolio.cards[1].queue_bucket, "resumable");
  assert.equal(portfolio.cards[1].current_cycle, 4);
  assert.equal(portfolio.cards[1].checkpoint_count, 4);
});

test("stale escalated historical blocker remains distinct from a brand-new blocker", () => {
  const staleEntry = buildHandoffMemoryEntry(
    buildPayload({
      session_id: "operator_session::stale",
      checkpoint_id: "operator_session::stale::checkpoint::0005",
      packet_id: "packet-stale",
    }),
  );
  const newBlockingEntry = buildHandoffMemoryEntry(
    buildPayload({
      session_id: "operator_session::current",
      checkpoint_id: "operator_session::current::checkpoint::0006",
      packet_id: "packet-current",
    }),
  );

  let memory = createEmptyAttentionMemory();
  memory = upsertHandoffMemory(memory, staleEntry).memory;
  memory = markHandoffEntryState(memory, staleEntry.session_id, staleEntry.entry_key, "acknowledged").memory;
  memory.sessions["operator_session::stale"].history[0].acknowledged_at = "2026-04-14T11:59:30Z";
  memory.sessions["operator_session::stale"].history[0].updated_at = "2026-04-14T11:59:30Z";
  memory = upsertHandoffMemory(memory, newBlockingEntry).memory;

  const portfolio = buildSessionPortfolio(memory, {
    currentSessionId: "operator_session::current",
    nowMs: Date.parse("2026-04-14T12:00:00Z"),
  });
  const staleCard = portfolio.cards.find((card) => card.session_id === "operator_session::stale");
  const currentCard = portfolio.cards.find((card) => card.session_id === "operator_session::current");
  assert.equal(staleCard?.queue_bucket, "stale_escalated_blocking");
  assert.equal(currentCard?.queue_bucket, "new_blocking_now");
  assert.notEqual(staleCard?.queue_bucket, currentCard?.queue_bucket);
});

test("halted review-results session is classified as completed history before live blockers", () => {
  const haltedEntry = buildHandoffMemoryEntry(
    buildPayload({
      session_id: "operator_session::halted",
      checkpoint_id: "operator_session::halted::checkpoint::0003",
      lifecycle_state: "halted",
      state_label: "Halted",
      stop_reason: "budget_exhausted",
      next_action: "Review results",
      next_action_detail: "Inspect the completed bounded session summary.",
      current_blocker: "Bounded run exhausted the total cycle budget.",
      blocking_count: 1,
    }),
  );
  assert.equal(classifyPortfolioSessionBucket(haltedEntry), "completed_halted");
});

test("max-cycle-exhausted intervention session remains a blocking session when review still gates continuation", () => {
  const exhaustedEntry = buildHandoffMemoryEntry(
    buildPayload({
      session_id: "operator_session::exhausted",
      checkpoint_id: "operator_session::exhausted::checkpoint::0003",
      lifecycle_state: "paused_for_intervention",
      state_label: "Review gate blocks continuation",
      stop_reason: "intervention_required",
      next_action: "Approve bounded continuation",
      next_action_detail: "Review the bounded evidence first, then approve, defer, or reject the next bounded step.",
      current_blocker: "No admissible implementation-bearing work item was available under the current directive.",
      current_cycle: 3,
      max_cycles: 3,
      policy_headroom_summary: "Continue one bounded step · 0 total cycle(s) remain · 2 cycle(s) per invocation.",
      blocking_count: 1,
    }),
  );
  assert.equal(classifyPortfolioSessionBucket(exhaustedEntry), "new_blocking_now");
});

test("portfolio navigation target deep-links current blockers to workspace and recent history to shell", () => {
  const currentBlockingCard = {
    session_id: "operator_session::current",
    entry_key: "current-entry",
    current_session: true,
    queue_bucket: "new_blocking_now",
  };
  const historicalResolvedCard = {
    session_id: "operator_session::history",
    entry_key: "history-entry",
    current_session: false,
    queue_bucket: "completed_halted",
  };

  const currentTarget = buildPortfolioNavigationTarget(currentBlockingCard);
  assert.equal(currentTarget.route, "/shell/workspace");
  assert.equal(currentTarget.focus, "current_blocker");
  assert.equal(currentTarget.session_id, "operator_session::current");
  assert.match(currentTarget.url, /portfolio_focus=current_blocker/);

  const historyTarget = buildPortfolioNavigationTarget(historicalResolvedCard);
  assert.equal(historyTarget.route, "/shell");
  assert.equal(historyTarget.focus, "portfolio_history");
  assert.equal(historyTarget.session_id, "operator_session::history");
  assert.match(historyTarget.url, /portfolio_focus=portfolio_history/);
});

test("resumable queue navigation keeps the targeted same session identity", () => {
  const resumableEntry = buildHandoffMemoryEntry(
    buildPayload({
      session_id: "operator_session::resumable",
      checkpoint_id: "operator_session::resumable::checkpoint::0007",
      severity: "clear",
      blocking_count: 0,
      informational_count: 0,
      lifecycle_state: "waiting_for_next_invocation",
      state_label: "Waiting for next invocation",
      stop_reason: "budget_boundary_reached",
      current_blocker: "No current blocker remains.",
      next_action: "Continue until next bounded stop",
      next_stop: "Budget boundary",
      checkpoint_count: 7,
      current_cycle: 7,
      resume_ready_after_next_action: true,
    }),
  );
  const bucket = classifyPortfolioSessionBucket(resumableEntry);
  assert.equal(bucket, "resumable");

  const target = buildPortfolioNavigationTarget({
    session_id: resumableEntry.session_id,
    entry_key: resumableEntry.entry_key,
    current_session: true,
    queue_bucket: bucket,
  });
  assert.equal(target.route, "/shell/workspace");
  assert.equal(target.focus, "continuation_controls");
  assert.equal(target.session_id, resumableEntry.session_id);
});
