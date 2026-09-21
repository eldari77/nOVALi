const STATUS_LABELS = {
  disabled: "Disabled",
  ready: "Ready",
  observed: "Observed",
  review_required: "Review required",
  review_blocked: "Review blocked",
  failed: "Failed",
};

const PORTAL_LABELS = {
  operator_confirmed: "LogicMonitor traces operator-confirmed",
  not_confirmed: "LogicMonitor traces not confirmed",
  not_recorded: "LogicMonitor trace confirmation not recorded",
};

export function buildReadOnlyAdapterStatusView(readOnlyAdapter) {
  const statusKey = String(readOnlyAdapter?.status || "ready").trim() || "ready";
  const reviewTickets = Array.isArray(readOnlyAdapter?.review_tickets)
    ? readOnlyAdapter.review_tickets
    : [];
  const latestReviewTicket = reviewTickets[0] || null;
  let detail =
    "Read-only adapter stays in observation-only mode and can summarize fixture snapshots without enabling mutation.";
  if (statusKey === "observed") {
    detail =
      "The latest read-only observation was recorded cleanly and remained evidence-only.";
  } else if (statusKey === "review_required") {
    detail =
      "A bounded read-only observation issue now sits in review evidence and needs operator attention.";
  } else if (statusKey === "review_blocked") {
    detail =
      "Critical read-only evidence is blocking continuation, such as mutation refusal or forbidden-domain content.";
  } else if (statusKey === "failed") {
    detail =
      "The latest read-only adapter proof failed, so validation, rollback, and immutability evidence should be inspected.";
  } else if (statusKey === "disabled") {
    detail = "The read-only adapter surface is disabled for this shell snapshot.";
  }
  const portalConfirmation =
    String(readOnlyAdapter?.lm_portal_trace_confirmation || "not_recorded").trim() ||
    "not_recorded";
  return {
    label: STATUS_LABELS[statusKey] || STATUS_LABELS.ready,
    statusKey,
    detail,
    mode:
      String(readOnlyAdapter?.mode || "fixture_read_only").trim() || "fixture_read_only",
    adapterName:
      String(readOnlyAdapter?.adapter_name || "static_fixture_read_only").trim() ||
      "static_fixture_read_only",
    adapterKind:
      String(readOnlyAdapter?.adapter_kind || "read_only_fixture").trim() ||
      "read_only_fixture",
    latestSnapshotId:
      String(readOnlyAdapter?.latest_snapshot_id || "").trim() || null,
    latestReplayPacketId:
      String(readOnlyAdapter?.latest_replay_packet_id || "").trim() || null,
    latestReviewTicketId:
      String(readOnlyAdapter?.latest_review_ticket_id || "").trim() || null,
    latestRollbackAnalysisId:
      String(readOnlyAdapter?.latest_rollback_analysis_id || "").trim() || null,
    latestMutationRefusalId:
      String(readOnlyAdapter?.latest_mutation_refusal_id || "").trim() || null,
    validationStatus:
      String(readOnlyAdapter?.validation_status || "unknown").trim() || "unknown",
    integrityStatus:
      String(readOnlyAdapter?.integrity_status || "unknown").trim() || "unknown",
    mutationRefusedCount: Number(readOnlyAdapter?.mutation_refused_count || 0),
    observationCount: Number(readOnlyAdapter?.observation_count || 0),
    badSnapshotCount: Number(readOnlyAdapter?.bad_snapshot_count || 0),
    staleSnapshotCount: Number(readOnlyAdapter?.stale_snapshot_count || 0),
    conflictingObservationCount: Number(readOnlyAdapter?.conflicting_observation_count || 0),
    laneId: String(readOnlyAdapter?.lane_id || "").trim() || null,
    laneAttributionStatus:
      String(readOnlyAdapter?.lane_attribution_status || "unknown").trim() || "unknown",
    reviewRequired: Boolean(readOnlyAdapter?.review_required),
    reviewReasons: Array.isArray(readOnlyAdapter?.review_reasons)
      ? readOnlyAdapter.review_reasons
      : [],
    latestReviewTicket,
    portalConfirmation,
    portalConfirmationLabel:
      PORTAL_LABELS[portalConfirmation] || PORTAL_LABELS.not_recorded,
    policyNotes: Array.isArray(readOnlyAdapter?.advisory_copy)
      ? readOnlyAdapter.advisory_copy
      : [
          "Read-only adapter: observation only.",
          "No real external-world mutation.",
          "Observation replay packets are evidence, not authority.",
          "Controller authority and review gates remain unchanged.",
          "No Space Engineers behavior is active.",
        ],
  };
}
