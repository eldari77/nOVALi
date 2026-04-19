import test from "node:test";
import assert from "node:assert/strict";

import { buildReadOnlyAdapterStatusView } from "../src/lib/readOnlyAdapterStatus.js";

test("buildReadOnlyAdapterStatusView maps ready defaults safely", () => {
  const view = buildReadOnlyAdapterStatusView(null);
  assert.equal(view.label, "Ready");
  assert.equal(view.mode, "fixture_read_only");
  assert.equal(view.observationCount, 0);
  assert.equal(view.portalConfirmationLabel, "LogicMonitor trace confirmation not recorded");
});

test("buildReadOnlyAdapterStatusView surfaces review-blocked state", () => {
  const view = buildReadOnlyAdapterStatusView({
    status: "review_blocked",
    adapter_name: "static_fixture_read_only",
    adapter_kind: "read_only_fixture",
    latest_snapshot_id: "snapshot_mutation_request",
    latest_replay_packet_id: "read-only-replay-1",
    latest_review_ticket_id: "read-only-review-1",
    latest_rollback_analysis_id: "read-only-rollback-1",
    latest_mutation_refusal_id: "mutation-refusal-1",
    validation_status: "failed",
    integrity_status: "failed",
    mutation_refused_count: 1,
    observation_count: 4,
    bad_snapshot_count: 3,
    stale_snapshot_count: 1,
    conflicting_observation_count: 1,
    lane_id: "lane_director",
    lane_attribution_status: "review_required",
    review_required: true,
    review_reasons: ["read_only_mutation_requested"],
    lm_portal_trace_confirmation: "operator_confirmed",
  });
  assert.equal(view.label, "Review blocked");
  assert.equal(view.latestReviewTicketId, "read-only-review-1");
  assert.equal(view.latestMutationRefusalId, "mutation-refusal-1");
  assert.equal(view.mutationRefusedCount, 1);
  assert.equal(view.portalConfirmationLabel, "LogicMonitor traces operator-confirmed");
});
