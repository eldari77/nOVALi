import test from "node:test";
import assert from "node:assert/strict";

import {
  buildHandoffMemoryEntry,
  classifyAttentionArchiveState,
  createEmptyAttentionMemory,
  filterAttentionArchiveEntries,
  markHandoffEntryState,
  pickAttentionFocusTarget,
  summarizeCurrentSessionMemory,
  upsertHandoffMemory,
} from "../src/lib/attentionMemory.js";

function buildPayload(overrides = {}) {
  const sessionId = overrides.session_id || "operator_session::test";
  const checkpointId = overrides.checkpoint_id || `${sessionId}::checkpoint::0003`;
  return {
    longRunState: {
      long_run: {
        session_id: sessionId,
        lifecycle_state: overrides.lifecycle_state || "paused_for_intervention",
        latest_checkpoint_id: checkpointId,
        last_checkpoint_at: overrides.checkpoint_at || "2026-04-13T17:00:00Z",
        halt_reason: overrides.stop_reason || "intervention_required",
      },
      operator_guidance: {
        session_handle: overrides.session_handle || "session-0003",
      },
    },
    attentionSignal: {
      severity: overrides.severity || "blocking",
      packet_id: overrides.packet_id || "packet-0003",
      blocking_count: overrides.blocking_count ?? 1,
      informational_count: overrides.informational_count ?? 0,
    },
    campaignHandoff: {
      label: "Campaign handoff summary",
      session_id: sessionId,
      session_handle: overrides.session_handle || "session-0003",
      lifecycle_state: overrides.lifecycle_state || "paused_for_intervention",
      state_label: overrides.state_label || "Paused for intervention",
      last_checkpoint_id: checkpointId,
      last_checkpoint_at: overrides.checkpoint_at || "2026-04-13T17:00:00Z",
      what_changed_summary: overrides.what_changed_summary || "1 checkpoint added; 1 cycle completed; review packet created.",
      current_blocker: overrides.current_blocker || "Review packet requires operator attention.",
      recommended_next_action_label: overrides.next_action || "Resolve intervention packet",
      recommended_next_action_detail: "Review the bounded packet and then continue the same session.",
      next_stop_boundary_label: overrides.next_stop || "Intervention review",
      attention_blocking_count: overrides.blocking_count ?? 1,
      attention_informational_count: overrides.informational_count ?? 0,
      resume_ready_after_next_action: true,
    },
    deltaSinceLastResume: {
      summary: overrides.delta_summary || "1 checkpoint added; 1 cycle completed.",
    },
  };
}

test("blocking attention entry is new and browser-notification eligible", () => {
  const entry = buildHandoffMemoryEntry(buildPayload());
  assert.equal(entry.local_state, "new");
  assert.equal(entry.notification_candidate, true);
  const result = upsertHandoffMemory(createEmptyAttentionMemory(), entry, {
    notificationSupport: { supported: true, permission: "granted" },
  });
  assert.equal(result.shouldNotify, true);
  assert.equal(result.notificationMode, "browser");
  assert.equal(result.currentEntry.local_state, "new");
});

test("informational attention stays distinct from resolved and does not notify urgently", () => {
  const entry = buildHandoffMemoryEntry(
    buildPayload({
      severity: "informational",
      blocking_count: 0,
      informational_count: 2,
      current_blocker: "Non-blocking packet is available for awareness.",
      next_action: "Review results",
      next_stop: "Budget boundary",
      lifecycle_state: "waiting_for_next_invocation",
      state_label: "Waiting for next invocation",
      stop_reason: "budget_boundary_reached",
    }),
  );
  assert.equal(entry.local_state, "new");
  assert.equal(entry.notification_candidate, false);
  const result = upsertHandoffMemory(createEmptyAttentionMemory(), entry, {
    notificationSupport: { supported: true, permission: "granted" },
  });
  assert.equal(result.shouldNotify, false);
  assert.equal(result.currentEntry.attention_informational_count, 2);
  assert.equal(result.currentEntry.local_state, "new");
});

test("seen acknowledged and resolved states round-trip without overriding blocking truth", () => {
  const entry = buildHandoffMemoryEntry(buildPayload());
  let result = upsertHandoffMemory(createEmptyAttentionMemory(), entry, {
    notificationSupport: { supported: true, permission: "granted" },
  });
  result = markHandoffEntryState(result.memory, entry.session_id, entry.entry_key, "seen");
  let summary = summarizeCurrentSessionMemory(result.memory, entry.session_id);
  assert.equal(summary.currentEntry.local_state, "seen");
  assert.equal(summary.currentEntry.attention_blocking_count, 1);
  assert.equal(summary.currentEntry.active, true);

  result = markHandoffEntryState(result.memory, entry.session_id, entry.entry_key, "acknowledged");
  summary = summarizeCurrentSessionMemory(result.memory, entry.session_id);
  assert.equal(summary.currentEntry.local_state, "acknowledged");
  assert.equal(summary.currentEntry.attention_blocking_count, 1);
  assert.equal(summary.acknowledgedBlockingCount, 1);

  const resolvedEntry = buildHandoffMemoryEntry(
    buildPayload({
      checkpoint_id: "operator_session::test::checkpoint::0004",
      packet_id: "",
      severity: "clear",
      blocking_count: 0,
      informational_count: 0,
      current_blocker: "No blocking attention remains.",
      next_action: "Continue until next bounded stop",
      next_stop: "Budget boundary",
      lifecycle_state: "waiting_for_next_invocation",
      state_label: "Waiting for next invocation",
      stop_reason: "budget_boundary_reached",
      what_changed_summary: "Blocking packet resolved and the same session is ready for the next bounded step.",
    }),
  );
  result = upsertHandoffMemory(result.memory, resolvedEntry, {
    notificationSupport: { supported: true, permission: "granted" },
  });
  summary = summarizeCurrentSessionMemory(result.memory, entry.session_id);
  assert.equal(summary.currentEntry.local_state, "resolved");
  assert.equal(summary.currentEntry.active, false);
  assert.equal(summary.resolvedCount >= 1, true);
});

test("unchanged already-seen blocking packet does not re-notify", () => {
  const entry = buildHandoffMemoryEntry(buildPayload());
  let result = upsertHandoffMemory(createEmptyAttentionMemory(), entry, {
    notificationSupport: { supported: true, permission: "granted" },
  });
  result = markHandoffEntryState(result.memory, entry.session_id, entry.entry_key, "seen");
  const repeated = upsertHandoffMemory(result.memory, entry, {
    notificationSupport: { supported: true, permission: "granted" },
  });
  assert.equal(repeated.shouldNotify, false);
  const summary = summarizeCurrentSessionMemory(repeated.memory, entry.session_id);
  assert.equal(summary.currentEntry.local_state, "seen");
  assert.equal(summary.unreadBlockingCount, 0);
  assert.equal(summary.seenBlockingCount, 1);
});

test("durable handoff history preserves session and checkpoint truth and stays bounded", () => {
  let memory = createEmptyAttentionMemory();
  for (let index = 1; index <= 10; index += 1) {
    const entry = buildHandoffMemoryEntry(
      buildPayload({
        checkpoint_id: `operator_session::test::checkpoint::${String(index).padStart(4, "0")}`,
        packet_id: `packet-${String(index).padStart(4, "0")}`,
        what_changed_summary: `${index} checkpoint packet`,
      }),
    );
    memory = upsertHandoffMemory(memory, entry, {
      notificationSupport: { supported: false, permission: "default" },
    }).memory;
  }
  const summary = summarizeCurrentSessionMemory(memory, "operator_session::test");
  assert.equal(summary.currentEntry.session_id, "operator_session::test");
  assert.equal(summary.currentEntry.checkpoint_id, "operator_session::test::checkpoint::0010");
  assert.equal(summary.history.length, 8);
  assert.equal(summary.history[0].checkpoint_id, "operator_session::test::checkpoint::0010");
});

test("archive state classification distinguishes new seen acknowledged resolved and informational history", () => {
  const blockingEntry = buildHandoffMemoryEntry(buildPayload());
  assert.equal(classifyAttentionArchiveState(blockingEntry), "new_blocking");

  let result = upsertHandoffMemory(createEmptyAttentionMemory(), blockingEntry, {
    notificationSupport: { supported: false, permission: "default" },
  });
  result = markHandoffEntryState(result.memory, blockingEntry.session_id, blockingEntry.entry_key, "seen");
  let summary = summarizeCurrentSessionMemory(result.memory, blockingEntry.session_id);
  assert.equal(classifyAttentionArchiveState(summary.currentEntry), "seen_unresolved_blocking");

  result = markHandoffEntryState(result.memory, blockingEntry.session_id, blockingEntry.entry_key, "acknowledged");
  summary = summarizeCurrentSessionMemory(result.memory, blockingEntry.session_id);
  assert.equal(classifyAttentionArchiveState(summary.currentEntry), "acknowledged_unresolved_blocking");

  const informationalEntry = buildHandoffMemoryEntry(
    buildPayload({
      checkpoint_id: "operator_session::test::checkpoint::0004",
      packet_id: "",
      severity: "informational",
      blocking_count: 0,
      informational_count: 1,
      stop_reason: "budget_boundary_reached",
      lifecycle_state: "waiting_for_next_invocation",
      state_label: "Waiting for next invocation",
      current_blocker: "Informational packet only.",
      next_action: "Review results",
    }),
  );
  result = upsertHandoffMemory(result.memory, informationalEntry, {
    notificationSupport: { supported: false, permission: "default" },
  });
  summary = summarizeCurrentSessionMemory(result.memory, blockingEntry.session_id);
  assert.equal(classifyAttentionArchiveState(summary.currentEntry), "informational_history");

  const resolvedEntry = buildHandoffMemoryEntry(
    buildPayload({
      checkpoint_id: "operator_session::test::checkpoint::0005",
      packet_id: "",
      severity: "clear",
      blocking_count: 0,
      informational_count: 0,
      stop_reason: "budget_boundary_reached",
      lifecycle_state: "waiting_for_next_invocation",
      state_label: "Waiting for next invocation",
      current_blocker: "No blocking attention remains.",
      next_action: "Continue until next bounded stop",
    }),
  );
  result = upsertHandoffMemory(result.memory, resolvedEntry, {
    notificationSupport: { supported: false, permission: "default" },
  });
  summary = summarizeCurrentSessionMemory(result.memory, blockingEntry.session_id);
  assert.equal(classifyAttentionArchiveState(summary.currentEntry), "resolved_history");
});

test("pick attention focus target chooses the exact blocking item before packet fallback", () => {
  const target = pickAttentionFocusTarget({
    currentPrimaryReviewItemId: "review-item-0007",
    attentionPacket: {
      packet_id: "packet-0007",
    },
    blockingItems: [
      {
        review_item_id: "review-item-0008",
        blocks_continuation: true,
      },
    ],
  });
  assert.deepEqual(target, {
    kind: "blocking_item",
    target_id: "attention-review-item-review-item-0007",
    reason: "current_primary_review_item",
  });

  const packetTarget = pickAttentionFocusTarget({
    attentionPacket: {
      packet_id: "packet-0009",
    },
    blockingItems: [
      {
        blocks_continuation: true,
      },
    ],
  });
  assert.deepEqual(packetTarget, {
    kind: "packet",
    target_id: "attention-packet-packet-0009",
    reason: "attention_packet",
  });
});

test("acknowledged unresolved blockers escalate to stale without reclassifying as new", () => {
  const entry = buildHandoffMemoryEntry(buildPayload());
  let result = upsertHandoffMemory(createEmptyAttentionMemory(), entry, {
    notificationSupport: { supported: false, permission: "default" },
  });
  result = markHandoffEntryState(result.memory, entry.session_id, entry.entry_key, "acknowledged");
  const staleMemory = structuredClone(result.memory);
  staleMemory.sessions[entry.session_id].history[0].acknowledged_at = "2026-04-13T16:59:30Z";
  staleMemory.sessions[entry.session_id].history[0].updated_at = "2026-04-13T16:59:30Z";
  const staleEntry = summarizeCurrentSessionMemory(staleMemory, entry.session_id).currentEntry;
  assert.equal(
    classifyAttentionArchiveState(staleEntry, { nowMs: Date.parse("2026-04-13T17:00:00Z") }),
    "stale_escalated_blocking",
  );
  assert.notEqual(
    classifyAttentionArchiveState(staleEntry, { nowMs: Date.parse("2026-04-13T17:00:00Z") }),
    "new_blocking",
  );
});

test("archive triage filters preserve lineage while isolating stale unresolved blockers", () => {
  const sessionId = "operator_session::test";
  const resolvedEntry = buildHandoffMemoryEntry(
    buildPayload({
      session_id: sessionId,
      checkpoint_id: `${sessionId}::checkpoint::0004`,
      packet_id: "",
      severity: "clear",
      blocking_count: 0,
      informational_count: 0,
      stop_reason: "budget_boundary_reached",
      lifecycle_state: "waiting_for_next_invocation",
      state_label: "Waiting for next invocation",
      current_blocker: "No blocking attention remains.",
      next_action: "Continue until next bounded stop",
    }),
  );
  let result = upsertHandoffMemory(createEmptyAttentionMemory(), resolvedEntry, {
    notificationSupport: { supported: false, permission: "default" },
  });

  const currentStale = buildHandoffMemoryEntry(
    buildPayload({
      session_id: sessionId,
      checkpoint_id: `${sessionId}::checkpoint::0005`,
      packet_id: "packet-0005",
    }),
  );
  result = upsertHandoffMemory(result.memory, currentStale, {
    notificationSupport: { supported: false, permission: "default" },
  });
  result = markHandoffEntryState(result.memory, sessionId, currentStale.entry_key, "acknowledged");
  result.memory.sessions[sessionId].history[0].acknowledged_at = "2026-04-13T16:59:30Z";

  const summary = summarizeCurrentSessionMemory(result.memory, sessionId);
  const staleEntries = filterAttentionArchiveEntries(summary.history, "stale", {
    currentEntryKey: currentStale.entry_key,
    nowMs: Date.parse("2026-04-13T17:00:00Z"),
  });
  assert.equal(staleEntries.length, 1);
  assert.equal(staleEntries[0].session_id, sessionId);
  assert.equal(staleEntries[0].checkpoint_id, `${sessionId}::checkpoint::0005`);

  const resolvedEntries = filterAttentionArchiveEntries(summary.history, "resolved", {
    currentEntryKey: currentStale.entry_key,
  });
  assert.equal(resolvedEntries.length >= 1, true);
  assert.equal(resolvedEntries[0].session_id, sessionId);
});
