const STATUS_LABELS = {
  clear: "Clear",
  raised: "Raised",
  acknowledged: "Acknowledged",
  reviewed: "Reviewed",
  blocked_waiting_operator: "Blocked waiting for operator",
  failed: "Failed",
};

const PORTAL_LABELS = {
  operator_confirmed: "LogicMonitor traces operator-confirmed",
  not_confirmed: "LogicMonitor traces not confirmed",
  not_recorded: "LogicMonitor trace confirmation not recorded",
};

export function buildOperatorAlertsStatusView(operatorAlerts) {
  const statusKey = String(operatorAlerts?.status || "clear").trim() || "clear";
  const alerts = Array.isArray(operatorAlerts?.alerts) ? operatorAlerts.alerts : [];
  const latestAlert = alerts[0] || null;
  let detail = "Local operator alerts stay evidence-only and do not approve action or mutation.";
  if (statusKey === "raised") {
    detail = "New operator-facing evidence signals are raised and waiting for acknowledgement or review.";
  } else if (statusKey === "acknowledged") {
    detail = "An operator has seen the alert evidence, but acknowledgement is not approval.";
  } else if (statusKey === "reviewed") {
    detail = "Alert evidence has been reviewed locally, but review still does not authorize action.";
  } else if (statusKey === "blocked_waiting_operator") {
    detail = "Critical evidence is blocking the affected line until the operator reviews the linked evidence bundle.";
  } else if (statusKey === "failed") {
    detail = "The local alert loop has failed and its evidence bundle integrity should be inspected.";
  }

  const portalConfirmation =
    String(operatorAlerts?.lm_portal_trace_confirmation || "not_recorded").trim() ||
    "not_recorded";

  return {
    label: STATUS_LABELS[statusKey] || STATUS_LABELS.clear,
    statusKey,
    detail,
    alertCount: Number(operatorAlerts?.alert_count || 0),
    raisedCount: Number(operatorAlerts?.raised_count || 0),
    acknowledgedCount: Number(operatorAlerts?.acknowledged_count || 0),
    reviewedCount: Number(operatorAlerts?.reviewed_count || 0),
    blockedCount: Number(operatorAlerts?.blocked_count || 0),
    criticalCount: Number(operatorAlerts?.critical_count || 0),
    highCount: Number(operatorAlerts?.high_count || 0),
    warningCount: Number(operatorAlerts?.warning_count || 0),
    latestAlertId: String(operatorAlerts?.latest_alert_id || "").trim() || null,
    latestAlertType: String(operatorAlerts?.latest_alert_type || "").trim() || null,
    latestEvidenceBundleId:
      String(operatorAlerts?.latest_evidence_bundle_id || "").trim() || null,
    latestOperatorActionRequired:
      String(operatorAlerts?.latest_operator_action_required || "").trim() || null,
    latestAcknowledgedAt:
      String(operatorAlerts?.latest_acknowledged_at || "").trim() || null,
    latestReviewedAt: String(operatorAlerts?.latest_reviewed_at || "").trim() || null,
    latestStatus: String(operatorAlerts?.latest_status || "").trim() || null,
    latestSeverity: String(operatorAlerts?.latest_severity || "").trim() || null,
    readOnlyAlertCount: Number(operatorAlerts?.read_only_alert_count || 0),
    telemetryAlertCandidateCount: Number(operatorAlerts?.telemetry_alert_candidate_count || 0),
    telemetryShutdownAlertCount: Number(operatorAlerts?.telemetry_shutdown_alert_count || 0),
    latestTelemetryShutdownAlertId:
      String(operatorAlerts?.latest_telemetry_shutdown_alert_id || "").trim() || null,
    identityBleedAlertCount: Number(operatorAlerts?.identity_bleed_alert_count || 0),
    latestAlert,
    availableActions: Array.isArray(operatorAlerts?.available_actions)
      ? operatorAlerts.available_actions
      : [],
    portalConfirmation,
    portalConfirmationLabel:
      PORTAL_LABELS[portalConfirmation] || PORTAL_LABELS.not_recorded,
    policyNotes: Array.isArray(operatorAlerts?.advisory_copy)
      ? operatorAlerts.advisory_copy
      : [
          "Alerts are evidence signals, not authority.",
          "Acknowledgement is not approval.",
          "No real external-world mutation.",
          "Controller authority and review gates remain unchanged.",
          "No Space Engineers behavior is active.",
        ],
  };
}
