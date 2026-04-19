import test from "node:test";
import assert from "node:assert/strict";

import { buildExternalAdapterStatusView } from "../src/lib/externalAdapterStatus.js";

test("buildExternalAdapterStatusView maps ready defaults safely", () => {
  const view = buildExternalAdapterStatusView(null);
  assert.equal(view.label, "Ready");
  assert.equal(view.mode, "mock_only");
  assert.equal(view.adapterName, "mock_external_world");
  assert.equal(view.portalConfirmationLabel, "LogicMonitor trace confirmation not recorded");
});

test("buildExternalAdapterStatusView surfaces review and kill switch state", () => {
  const view = buildExternalAdapterStatusView({
    status: "kill_switch_triggered",
    last_proof_result: "success",
    last_action_status: "kill_switch_triggered",
    last_review_required: true,
    review_reasons: ["kill switch triggered", "rollback ambiguity"],
    replay_packet_count: 6,
    last_replay_packet_id: "replay-123",
    kill_switch_state: "triggered",
    telemetry_enabled: true,
    lm_portal_trace_confirmation: "operator_confirmed",
  });
  assert.equal(view.label, "Kill switch triggered");
  assert.equal(view.proofLabel, "Mock adapter proof succeeded");
  assert.equal(view.lastActionStatus, "kill_switch_triggered");
  assert.equal(view.replayPacketCount, 6);
  assert.equal(view.lastReplayPacketId, "replay-123");
  assert.equal(view.killSwitchState, "triggered");
  assert.equal(view.portalConfirmationLabel, "LogicMonitor traces operator-confirmed");
  assert.equal(view.lastReviewRequired, true);
  assert.deepEqual(view.reviewReasons, ["kill switch triggered", "rollback ambiguity"]);
});
