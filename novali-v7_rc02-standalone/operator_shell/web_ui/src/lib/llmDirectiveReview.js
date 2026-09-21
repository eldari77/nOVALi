const text = (...values) => {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    const next = String(value).trim();
    if (next) return next;
  }
  return "";
};

export function selectLatestDirectiveDraft(history) {
  const records = Array.isArray(history?.records) ? history.records : [];
  for (const record of records) {
    const directiveText = text(
      record?.assistant_response_redacted,
      record?.assistant_text,
      record?.response_preview,
      record?.response,
    );
    if (
      text(record?.mode) === "draft_directive" &&
      text(record?.status, "completed") === "completed" &&
      directiveText
    ) {
      return {
        ...record,
        record_id: text(record?.record_id, record?.id),
        directive_text: directiveText,
      };
    }
  }
  return {};
}

export function selectLatestDirectiveDraftAttempt(history) {
  const records = Array.isArray(history?.records) ? history.records : [];
  for (const record of records) {
    if (text(record?.mode) !== "draft_directive") continue;
    const attemptSummary = text(
      record?.assistant_response_redacted,
      record?.assistant_text,
      record?.response_preview,
      record?.response,
      record?.error_summary_redacted,
      record?.error,
      "No response stored yet.",
    );
    return {
      ...record,
      record_id: text(record?.record_id, record?.id),
      status: text(record?.status, "unknown"),
      attempt_summary: attemptSummary,
    };
  }
  return {};
}

export function buildLLMProgressModel(record) {
  const status = text(record?.status, "unknown").toLowerCase();
  const phase = text(record?.llm_progress_phase, status);
  const maxRepairAttempts = Number(record?.max_repair_attempts ?? 3);
  const malformedRetryCount = Number(record?.malformed_retry_count ?? 0);
  const currentAttemptIndex = Number(record?.current_attempt_index ?? 1);
  const rawPercent = Number(record?.llm_progress_percent ?? 0);
  const percent = Math.max(0, Math.min(100, Number.isFinite(rawPercent) ? rawPercent : 0));
  const active = status === "in_progress";
  let phaseLabel = "Starting";
  if (phase === "attempt") phaseLabel = `Attempt ${currentAttemptIndex}`;
  if (phase === "repair_attempt") phaseLabel = `Repair attempt ${malformedRetryCount}/${maxRepairAttempts}`;
  if (phase === "completed" || status === "completed") phaseLabel = "Completed";
  if (phase === "failed" || ["timeout", "malformed_response", "unavailable", "error"].includes(status)) {
    phaseLabel = "Failed";
  }
  const detail = text(
    record?.latest_repair_feedback,
    status === "malformed_response" && malformedRetryCount
      ? `${malformedRetryCount} repair attempts completed without usable message.content.`
      : "",
    active ? "Novali is waiting for the local model." : "",
  );
  return {
    active,
    percent,
    phase,
    phaseLabel,
    detail,
    recordId: text(record?.record_id, record?.id),
    currentAttemptIndex,
    maxRepairAttempts,
    malformedRetryCount,
  };
}

export function buildDirectiveRevisionPrompt({ draftText, feedback }) {
  return [
    "Revise this directive draft using the operator feedback below.",
    "Return only the complete revised directive draft. Keep safety, scope, review gates, and conveyor suitability explicit.",
    "",
    "Operator feedback:",
    text(feedback, "No additional feedback provided."),
    "",
    "Current directive draft:",
    text(draftText),
  ].join("\n");
}

export function directiveDraftCompleteness(draftText) {
  const draft = text(draftText);
  const lower = draft.toLowerCase();
  const checks = [
    ["missing_directive_title", /directive\s*:/i.test(draft) || /^#?\s*directive\b/i.test(draft)],
    ["missing_mission", lower.includes("mission")],
    ["missing_objectives", lower.includes("objectives")],
    ["missing_deliverables", lower.includes("deliverables")],
    ["missing_success_criteria", lower.includes("success criteria")],
    ["missing_stop_conditions", lower.includes("stop conditions")],
  ];
  const reasons = checks.filter(([, passed]) => !passed).map(([reason]) => reason);
  const trailingFragments = [
    "document assumptions",
    "major scope expansion,",
    "and",
    "or",
  ];
  const trimmed = draft.trim().toLowerCase();
  if (trailingFragments.some((fragment) => trimmed.endsWith(fragment))) {
    reasons.push("appears_truncated");
  }
  return {
    complete: reasons.length === 0,
    reasons,
  };
}

export function buildConveyorPayloadFromDraft(draft) {
  const directiveText = text(draft?.directive_text, draft?.assistant_response_redacted);
  const completeness = directiveDraftCompleteness(directiveText);
  return {
    directive_text: completeness.complete ? directiveText : "",
    source_kind: "operator",
    requested_by: "operator",
    priority: 5,
    metadata: {
      source_kind: "ask_novali_draft",
      source_record_id: text(draft?.record_id, draft?.id),
      approved_from_ui: true,
      draft_complete: completeness.complete,
      draft_completeness_reasons: completeness.reasons,
    },
  };
}
