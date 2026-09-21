const STATUS_LABELS = {
  disabled: "Disabled",
  ready: "Ready",
  review_required: "Review required",
  failed: "Failed",
  kill_switch_triggered: "Kill switch triggered",
};

const PROOF_LABELS = {
  unknown: "Mock adapter proof pending",
  success: "Mock adapter proof succeeded",
  failure: "Mock adapter proof failed",
  skipped: "Mock adapter proof skipped",
};

const LM_PORTAL_LABELS = {
  operator_confirmed: "LogicMonitor traces operator-confirmed",
  not_confirmed: "LogicMonitor traces not confirmed",
  not_recorded: "LogicMonitor trace confirmation not recorded",
};

export function buildExternalAdapterStatusView(externalAdapter) {
  const statusKey = String(externalAdapter?.status || "ready").trim() || "ready";
  const proofResult = String(externalAdapter?.last_proof_result || "unknown").trim() || "unknown";
  const reviewReasons = Array.isArray(externalAdapter?.review_reasons)
    ? externalAdapter.review_reasons
    : [];
  const portalConfirmation =
    String(externalAdapter?.lm_portal_trace_confirmation || "not_recorded").trim() ||
    "not_recorded";
  let detail = "Mock adapter membrane is ready for bounded proof-only execution.";
  if (statusKey === "review_required") {
    detail = "The last mock adapter run raised review-required state and preserved replay evidence.";
  } else if (statusKey === "failed") {
    detail = "The last mock adapter proof failed, so replay evidence and redaction posture should be inspected.";
  } else if (statusKey === "kill_switch_triggered") {
    detail = "The mock-only kill switch is triggered for proof state; NOVALI itself remains running.";
  } else if (statusKey === "disabled") {
    detail = "The external adapter membrane is disabled in this shell snapshot.";
  }
  return {
    label: STATUS_LABELS[statusKey] || STATUS_LABELS.ready,
    statusKey,
    mode: String(externalAdapter?.mode || "mock_only").trim() || "mock_only",
    adapterName:
      String(externalAdapter?.adapter_name || "mock_external_world").trim() ||
      "mock_external_world",
    adapterKind: String(externalAdapter?.adapter_kind || "mock").trim() || "mock",
    schemaVersion: String(externalAdapter?.schema_version || "rc85.v1").trim() || "rc85.v1",
    proofResult,
    proofLabel: PROOF_LABELS[proofResult] || PROOF_LABELS.unknown,
    detail,
    lastActionStatus:
      String(externalAdapter?.last_action_status || "").trim() || "n/a",
    lastReviewRequired: Boolean(externalAdapter?.last_review_required),
    reviewReasons,
    replayPacketCount: Number(externalAdapter?.replay_packet_count || 0),
    lastReplayPacketId:
      String(externalAdapter?.last_replay_packet_id || "").trim() || null,
    lastReviewItemId:
      String(externalAdapter?.last_review_item_id || "").trim() || null,
    lastRollbackAnalysisId:
      String(externalAdapter?.last_rollback_analysis_id || "").trim() || null,
    killSwitchState:
      String(externalAdapter?.kill_switch_state || "inactive").trim() || "inactive",
    telemetryEnabled: Boolean(externalAdapter?.telemetry_enabled),
    portalConfirmation,
    portalConfirmationLabel:
      LM_PORTAL_LABELS[portalConfirmation] || LM_PORTAL_LABELS.not_recorded,
    policyNotes: [
      "External adapter membrane: mock only.",
      "No real external-world mutation.",
      "Replay packets are evidence, not authority.",
      "Controller authority and review gates remain unchanged.",
      "LogicMonitor visibility is evidence only.",
      "Future game/server adapters remain deferred.",
    ],
  };
}
