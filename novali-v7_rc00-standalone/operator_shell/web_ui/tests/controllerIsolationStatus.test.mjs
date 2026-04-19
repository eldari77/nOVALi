import test from "node:test";
import assert from "node:assert/strict";

import { buildControllerIsolationStatusView } from "../src/lib/controllerIsolationStatus.js";

test("buildControllerIsolationStatusView maps ready defaults safely", () => {
  const view = buildControllerIsolationStatusView(null);
  assert.equal(view.label, "Ready");
  assert.equal(view.laneCount, 0);
  assert.equal(view.findingCount, 0);
  assert.equal(view.portalConfirmationLabel, "LogicMonitor trace confirmation not recorded");
});

test("buildControllerIsolationStatusView surfaces review-blocked state", () => {
  const view = buildControllerIsolationStatusView({
    status: "review_blocked",
    lane_count: 3,
    lanes: [
      { lane_role: "director" },
      { lane_role: "sovereign_good" },
      { lane_role: "sovereign_dark" },
    ],
    identity_bleed: {
      finding_count: 4,
      high_count: 2,
      critical_count: 2,
      latest_finding_id: "isolation-finding-1",
      latest_review_ticket_id: "isolation-review-1",
    },
    cross_lane_messages: {
      proposed_count: 3,
      approved_count: 1,
      blocked_count: 2,
      unauthorized_count: 2,
      latest_message_id: "lane-message-1",
    },
    isolation_checks: {
      namespace_separation: "fail",
      no_hidden_shared_scratchpad: "fail",
      director_channel_required: "fail",
      telemetry_lane_identity: "pass",
    },
    latest_replay_packet_id: "isolation-replay-1",
    review_tickets: [
      {
        review_ticket_id: "isolation-review-1",
        review_reasons: ["unauthorized_authority_claim"],
      },
    ],
    lm_portal_trace_confirmation: "operator_confirmed",
  });
  assert.equal(view.label, "Review blocked");
  assert.equal(view.laneCount, 3);
  assert.equal(view.findingCount, 4);
  assert.equal(view.latestReviewTicketId, "isolation-review-1");
  assert.equal(view.latestReplayPacketId, "isolation-replay-1");
  assert.equal(view.portalConfirmationLabel, "LogicMonitor traces operator-confirmed");
  assert.deepEqual(view.laneRoles, ["director", "sovereign_good", "sovereign_dark"]);
});
