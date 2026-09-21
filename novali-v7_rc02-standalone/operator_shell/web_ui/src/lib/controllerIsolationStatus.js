const STATUS_LABELS = {
  disabled: "Disabled",
  ready: "Ready",
  review_required: "Review required",
  review_blocked: "Review blocked",
  failed: "Failed",
};

const CHECK_LABELS = {
  pass: "Pass",
  warning: "Warning",
  fail: "Fail",
};

const PORTAL_LABELS = {
  operator_confirmed: "LogicMonitor traces operator-confirmed",
  not_confirmed: "LogicMonitor traces not confirmed",
  not_recorded: "LogicMonitor trace confirmation not recorded",
};

export function buildControllerIsolationStatusView(controllerIsolation) {
  const statusKey = String(controllerIsolation?.status || "ready").trim() || "ready";
  const lanes = Array.isArray(controllerIsolation?.lanes) ? controllerIsolation.lanes : [];
  const identityBleed = controllerIsolation?.identity_bleed || {};
  const crossLaneMessages = controllerIsolation?.cross_lane_messages || {};
  const isolationChecks = controllerIsolation?.isolation_checks || {};
  const reviewTickets = Array.isArray(controllerIsolation?.review_tickets)
    ? controllerIsolation.review_tickets
    : [];
  const latestReviewTicket = reviewTickets[0] || null;
  let detail =
    "Lane identities are isolated mock namespaces only; no new runtime controller authority is created.";
  if (statusKey === "review_required") {
    detail =
      "Controller isolation findings are present and now sit in the existing review surface as evidence only.";
  } else if (statusKey === "review_blocked") {
    detail =
      "Critical isolation findings are blocking continuation until the operator reviews the lane-bleed evidence.";
  } else if (statusKey === "failed") {
    detail =
      "The latest isolation proof failed, so namespace separation and review evidence should be inspected.";
  } else if (statusKey === "disabled") {
    detail = "Controller isolation scaffolding is disabled for this shell snapshot.";
  }
  return {
    label: STATUS_LABELS[statusKey] || STATUS_LABELS.ready,
    statusKey,
    detail,
    laneCount: Number(controllerIsolation?.lane_count || lanes.length || 0),
    lanes,
    laneRoles: lanes.map((lane) => String(lane?.lane_role || "").trim()).filter(Boolean),
    latestReviewTicket,
    latestReviewTicketId:
      String(
        controllerIsolation?.latest_review_ticket_id ||
          identityBleed?.latest_review_ticket_id ||
          "",
      ).trim() || null,
    latestReplayPacketId:
      String(controllerIsolation?.latest_replay_packet_id || "").trim() || null,
    findingCount: Number(identityBleed?.finding_count || 0),
    highCount: Number(identityBleed?.high_count || 0),
    criticalCount: Number(identityBleed?.critical_count || 0),
    latestFindingId: String(identityBleed?.latest_finding_id || "").trim() || null,
    proposedCount: Number(crossLaneMessages?.proposed_count || 0),
    approvedCount: Number(crossLaneMessages?.approved_count || 0),
    blockedCount: Number(crossLaneMessages?.blocked_count || 0),
    unauthorizedCount: Number(crossLaneMessages?.unauthorized_count || 0),
    latestMessageId: String(crossLaneMessages?.latest_message_id || "").trim() || null,
    namespaceSeparationLabel:
      CHECK_LABELS[String(isolationChecks?.namespace_separation || "pass").trim() || "pass"] ||
      CHECK_LABELS.pass,
    hiddenScratchpadLabel:
      CHECK_LABELS[
        String(isolationChecks?.no_hidden_shared_scratchpad || "pass").trim() || "pass"
      ] || CHECK_LABELS.pass,
    directorChannelLabel:
      CHECK_LABELS[
        String(isolationChecks?.director_channel_required || "pass").trim() || "pass"
      ] || CHECK_LABELS.pass,
    telemetryIdentityLabel:
      CHECK_LABELS[
        String(isolationChecks?.telemetry_lane_identity || "pass").trim() || "pass"
      ] || CHECK_LABELS.pass,
    portalConfirmation:
      String(controllerIsolation?.lm_portal_trace_confirmation || "not_recorded").trim() ||
      "not_recorded",
    portalConfirmationLabel:
      PORTAL_LABELS[
        String(controllerIsolation?.lm_portal_trace_confirmation || "not_recorded").trim() ||
          "not_recorded"
      ] || PORTAL_LABELS.not_recorded,
    policyNotes: Array.isArray(controllerIsolation?.advisory_copy)
      ? controllerIsolation.advisory_copy
      : [
          "Identity lanes are isolation scaffolding, not independent controllers.",
          "No new adoption authority is created.",
          "Cross-lane communication must be Director-mediated and replayable.",
          "No Space Engineers behavior is active.",
        ],
  };
}
