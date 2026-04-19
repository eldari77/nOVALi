import test from "node:test";
import assert from "node:assert/strict";

import { buildExternalAdapterReviewStatusView } from "../src/lib/externalAdapterReviewStatus.js";

test("buildExternalAdapterReviewStatusView maps clear defaults safely", () => {
  const view = buildExternalAdapterReviewStatusView(null);
  assert.equal(view.label, "Clear");
  assert.equal(view.pendingCount, 0);
  assert.equal(view.restoreAllowed, false);
  assert.equal(view.restorePerformed, false);
});

test("buildExternalAdapterReviewStatusView surfaces escalated rollback state", () => {
  const view = buildExternalAdapterReviewStatusView({
    status: "escalated",
    pending_count: 3,
    escalated_count: 2,
    evidence_missing_count: 1,
    last_review_item_id: "ext-review-123",
    last_replay_packet_id: "replay-123",
    last_rollback_analysis_id: "rollback-123",
    last_checkpoint_ref: "mock-checkpoint-1",
    last_operator_action_required: "Inspect replay evidence",
    rollback_possible: true,
    rollback_candidate: true,
    checkpoint_available: true,
    restore_allowed: false,
    restore_performed: false,
    ambiguity_level: "high",
    review_items: [
      {
        review_item_id: "ext-review-123",
        review_reasons: ["rollback ambiguity", "missing replay packet"],
      },
    ],
  });
  assert.equal(view.label, "Escalated");
  assert.equal(view.pendingCount, 3);
  assert.equal(view.escalatedCount, 2);
  assert.equal(view.evidenceMissingCount, 1);
  assert.equal(view.lastReviewItemId, "ext-review-123");
  assert.equal(view.lastReplayPacketId, "replay-123");
  assert.equal(view.lastRollbackAnalysisId, "rollback-123");
  assert.equal(view.lastCheckpointRef, "mock-checkpoint-1");
  assert.equal(view.ambiguityLevel, "high");
  assert.deepEqual(view.lastReviewItem.review_reasons, [
    "rollback ambiguity",
    "missing replay packet",
  ]);
});
