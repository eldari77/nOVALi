import test from "node:test";
import assert from "node:assert/strict";

import { buildOperatorAlertsStatusView } from "../src/lib/operatorAlertsStatus.js";

test("buildOperatorAlertsStatusView maps clear defaults safely", () => {
  const view = buildOperatorAlertsStatusView(null);
  assert.equal(view.label, "Clear");
  assert.equal(view.alertCount, 0);
  assert.equal(view.portalConfirmationLabel, "LogicMonitor trace confirmation not recorded");
});

test("buildOperatorAlertsStatusView surfaces blocked operator alert detail", () => {
  const view = buildOperatorAlertsStatusView({
    status: "blocked_waiting_operator",
    alert_count: 5,
    raised_count: 2,
    blocked_count: 3,
    critical_count: 2,
    high_count: 1,
    warning_count: 2,
    latest_alert_id: "operator-alert-123",
    latest_alert_type: "read_only_mutation_requested",
    latest_evidence_bundle_id: "alert-evidence-123",
    latest_operator_action_required: "Inspect the linked evidence bundle.",
    latest_status: "blocked_waiting_operator",
    latest_severity: "critical",
    latest_acknowledged_at: "2026-04-19T18:00:00Z",
    latest_reviewed_at: "2026-04-19T18:05:00Z",
    read_only_alert_count: 4,
    telemetry_alert_candidate_count: 1,
    telemetry_shutdown_alert_count: 1,
    latest_telemetry_shutdown_alert_id: "operator-alert-shutdown-1",
    identity_bleed_alert_count: 1,
    lm_portal_trace_confirmation: "operator_confirmed",
    alerts: [
      {
        alert_id: "operator-alert-123",
        summary_redacted: "Mutation request refused and preserved as evidence.",
      },
    ],
    available_actions: [
      { action_id: "acknowledge_operator_alert", label: "acknowledge" },
      { action_id: "review_operator_alert", label: "mark reviewed" },
    ],
  });
  assert.equal(view.label, "Blocked waiting for operator");
  assert.equal(view.latestAlertId, "operator-alert-123");
  assert.equal(view.latestEvidenceBundleId, "alert-evidence-123");
  assert.equal(view.availableActions.length, 2);
  assert.equal(view.portalConfirmationLabel, "LogicMonitor traces operator-confirmed");
  assert.equal(view.telemetryShutdownAlertCount, 1);
  assert.equal(view.latestTelemetryShutdownAlertId, "operator-alert-shutdown-1");
});
