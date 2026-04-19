const STATUS_LABELS = {
  clear: "Clear",
  pending_review: "Pending review",
  escalated: "Escalated",
  blocked: "Blocked",
};

export function buildExternalAdapterReviewStatusView(externalAdapterReview) {
  const statusKey =
    String(externalAdapterReview?.status || "clear").trim() || "clear";
  const reviewItems = Array.isArray(externalAdapterReview?.review_items)
    ? externalAdapterReview.review_items
    : [];
  const lastReviewItem = reviewItems[0] || null;
  let detail =
    "No external adapter review item is currently blocking the mock-only membrane.";
  if (statusKey === "pending_review") {
    detail =
      "At least one mock adapter outcome now sits in Review Hold evidence and needs operator attention.";
  } else if (statusKey === "escalated") {
    detail =
      "Escalated mock adapter evidence is present; review the replay and rollback links before any further adapter work.";
  } else if (statusKey === "blocked") {
    detail =
      "The mock adapter is blocked by critical review evidence such as a kill switch or missing rollback clarity.";
  }
  return {
    label: STATUS_LABELS[statusKey] || STATUS_LABELS.clear,
    statusKey,
    detail,
    pendingCount: Number(externalAdapterReview?.pending_count || 0),
    escalatedCount: Number(externalAdapterReview?.escalated_count || 0),
    evidenceMissingCount: Number(externalAdapterReview?.evidence_missing_count || 0),
    lastReviewItemId:
      String(externalAdapterReview?.last_review_item_id || "").trim() || null,
    lastReplayPacketId:
      String(externalAdapterReview?.last_replay_packet_id || "").trim() || null,
    lastRollbackAnalysisId:
      String(externalAdapterReview?.last_rollback_analysis_id || "").trim() || null,
    lastCheckpointRef:
      String(externalAdapterReview?.last_checkpoint_ref || "").trim() || null,
    lastOperatorActionRequired:
      String(externalAdapterReview?.last_operator_action_required || "").trim() || null,
    rollbackPossible: Boolean(externalAdapterReview?.rollback_possible),
    rollbackCandidate: Boolean(externalAdapterReview?.rollback_candidate),
    checkpointAvailable: Boolean(externalAdapterReview?.checkpoint_available),
    restoreAllowed: Boolean(externalAdapterReview?.restore_allowed),
    restorePerformed: Boolean(externalAdapterReview?.restore_performed),
    ambiguityLevel:
      String(externalAdapterReview?.ambiguity_level || "none").trim() || "none",
    reviewItems,
    lastReviewItem,
    advisoryCopy: Array.isArray(externalAdapterReview?.advisory_copy)
      ? externalAdapterReview.advisory_copy
      : [
          "Review items are evidence only.",
          "Rollback analysis does not automatically restore state.",
          "No real external-world mutation is allowed in rc85.",
          "Controller authority and review gates remain unchanged.",
        ],
  };
}
