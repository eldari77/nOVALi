import test from "node:test";
import assert from "node:assert/strict";

import {
  buildHandoffMemoryEntry,
  createEmptyAttentionMemory,
  upsertHandoffMemory,
} from "../src/lib/attentionMemory.js";
import {
  buildPortfolioNavigationTarget,
  buildSessionPortfolio,
} from "../src/lib/sessionPortfolio.js";
import {
  buildManagedSessionPortfolio,
  createEmptyPortfolioLifecycleMemory,
} from "../src/lib/portfolioLifecycle.js";
import {
  applyPortfolioShortcutMemoryAction,
  buildPortfolioActionView,
  createEmptyPortfolioShortcutMemory,
} from "../src/lib/portfolioShortcuts.js";

function buildPayload(overrides = {}) {
  const sessionId = overrides.session_id || "operator_session::shortcut";
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

function buildManagedPortfolio() {
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
  const resumableSession = buildHandoffMemoryEntry(
    buildPayload({
      session_id: "operator_session::resumable",
      checkpoint_id: "operator_session::resumable::checkpoint::0006",
      severity: "informational",
      blocking_count: 0,
      informational_count: 0,
      lifecycle_state: "paused_for_budget",
      state_label: "Paused for budget",
      stop_reason: "budget_boundary_reached",
      current_blocker: "Ready to continue once the operator resumes the same session.",
      next_action: "Continue until next bounded stop",
      next_action_detail: "Resume the same session from the saved bounded checkpoint.",
      resume_ready_after_next_action: true,
    }),
  );

  let memory = createEmptyAttentionMemory();
  memory = upsertHandoffMemory(memory, completedHistory).memory;
  memory = upsertHandoffMemory(memory, informationalRecent).memory;
  memory = upsertHandoffMemory(memory, resumableSession).memory;
  memory = upsertHandoffMemory(memory, currentBlocking).memory;

  const portfolio = buildSessionPortfolio(memory, {
    currentSessionId: "operator_session::blocking",
  });
  return buildManagedSessionPortfolio(
    portfolio.cards,
    portfolio.recommendation,
    createEmptyPortfolioLifecycleMemory(),
  );
}

test("state-appropriate shortcuts distinguish direct portfolio actions from session-open actions", () => {
  const managed = buildManagedPortfolio();
  const actionView = buildPortfolioActionView(
    managed.sections,
    managed.recommendation,
    createEmptyPortfolioShortcutMemory(),
    [],
  );
  const blockingCard = actionView.cards.find((card) => card.session_id === "operator_session::blocking");
  const completedCard = actionView.cards.find((card) => card.session_id === "operator_session::completed");
  const resumableCard = actionView.cards.find((card) => card.session_id === "operator_session::resumable");

  assert.equal(blockingCard.shortcut_action_label, "Resolve blocker");
  assert.equal(blockingCard.shortcut_action_mode, "open_session");
  assert.equal(blockingCard.shortcut_requires_session_open, true);

  assert.equal(resumableCard.shortcut_action_label, "Continue session");
  assert.equal(resumableCard.shortcut_action_mode, "open_session");

  assert.equal(completedCard.shortcut_action_label, "Archive from queue");
  assert.equal(completedCard.shortcut_action_mode, "direct");
  assert.equal(completedCard.shortcut_requires_session_open, false);
});

test("blocked batch archive explains why true blockers stay discoverable", () => {
  const managed = buildManagedPortfolio();
  const initialView = buildPortfolioActionView(
    managed.sections,
    managed.recommendation,
    createEmptyPortfolioShortcutMemory(),
    [],
  );
  const blockingCard = initialView.cards.find((card) => card.session_id === "operator_session::blocking");
  const completedCard = initialView.cards.find((card) => card.session_id === "operator_session::completed");
  const actionView = buildPortfolioActionView(
    managed.sections,
    managed.recommendation,
    createEmptyPortfolioShortcutMemory(),
    [
      blockingCard.entry_key,
      completedCard.entry_key,
    ],
  );

  assert.equal(actionView.batch.actions.archive_selected.allowed, false);
  assert.match(
    actionView.batch.actions.archive_selected.blocked_reason,
    /discoverable|open those sessions/i,
  );
});

test("batch pin remains safe for mixed visible sessions and recommendation stays blocker-first", () => {
  const managed = buildManagedPortfolio();
  const initialView = buildPortfolioActionView(
    managed.sections,
    managed.recommendation,
    createEmptyPortfolioShortcutMemory(),
    [],
  );
  const blockingCard = initialView.cards.find((card) => card.session_id === "operator_session::blocking");
  const completedCard = initialView.cards.find((card) => card.session_id === "operator_session::completed");
  const actionView = buildPortfolioActionView(
    managed.sections,
    managed.recommendation,
    createEmptyPortfolioShortcutMemory(),
    [
      blockingCard.entry_key,
      completedCard.entry_key,
    ],
  );

  assert.equal(actionView.batch.actions.pin_selected.allowed, true);
  assert.equal(actionView.recommendation.target_session_id, "operator_session::blocking");
  assert.equal(
    actionView.cards.some((card) => card.session_id === "operator_session::blocking"),
    true,
  );
});

test("shortlist memory round-trips without changing session lineage", () => {
  const managed = buildManagedPortfolio();
  const initialView = buildPortfolioActionView(
    managed.sections,
    managed.recommendation,
    createEmptyPortfolioShortcutMemory(),
    [],
  );
  const completedCard = initialView.cards.find((card) => card.session_id === "operator_session::completed");

  const shortlistResult = applyPortfolioShortcutMemoryAction(
    createEmptyPortfolioShortcutMemory(),
    [completedCard],
    "shortlist",
  );
  const shortlistedView = buildPortfolioActionView(
    managed.sections,
    managed.recommendation,
    shortlistResult.memory,
    [completedCard.entry_key],
  );
  const shortlistedCard = shortlistedView.cards.find(
    (card) => card.session_id === "operator_session::completed",
  );

  assert.equal(shortlistedCard.shortlisted, true);
  assert.equal(shortlistedCard.session_id, completedCard.session_id);
  assert.equal(shortlistedCard.entry_key, completedCard.entry_key);
  assert.equal(shortlistedView.batch.actions.clear_shortlist_selected.allowed, true);
});

test("portfolio navigation keeps the same session target and blocker focus", () => {
  const managed = buildManagedPortfolio();
  const actionView = buildPortfolioActionView(
    managed.sections,
    managed.recommendation,
    createEmptyPortfolioShortcutMemory(),
    [],
  );
  const blockingCard = actionView.cards.find((card) => card.session_id === "operator_session::blocking");
  const navigation = buildPortfolioNavigationTarget(blockingCard);
  const url = new URL(`http://localhost${navigation.url}`);

  assert.equal(navigation.route, "/shell/workspace");
  assert.equal(url.searchParams.get("portfolio_session"), blockingCard.session_id);
  assert.equal(url.searchParams.get("portfolio_entry_key"), blockingCard.entry_key);
  assert.equal(url.searchParams.get("portfolio_focus"), "current_blocker");
});
