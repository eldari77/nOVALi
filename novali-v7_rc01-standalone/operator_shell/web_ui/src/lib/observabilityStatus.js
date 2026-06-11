const STATUS_LABELS = {
  disabled: "Disabled",
  configured: "Configured",
  exporting: "Exporting",
  degraded: "Collector unreachable",
  unavailable: "Unavailable",
};
const PROBE_LABELS = {
  success: "Live collector probe succeeded",
  failure: "Live collector probe failed",
  skipped: "Live collector probe skipped",
  unknown: "Live collector probe not yet run",
};
const VISIBILITY_LABELS = {
  success: "Trace visibility probe succeeded",
  failure: "Trace visibility probe failed",
  skipped: "Trace visibility probe skipped",
  unknown: "Trace visibility probe pending",
  not_recorded: "Trace visibility probe not recorded",
};
const PORTAL_CONFIRMATION_LABELS = {
  confirmed: "Portal visibility confirmed",
  not_confirmed: "Portal visibility not confirmed",
  not_recorded: "Portal visibility not recorded",
};
const DOCKERIZED_PROBE_LABELS = {
  success: "Dockerized agent telemetry proof: succeeded.",
  failure: "Dockerized agent telemetry proof: failed.",
  skipped: "Dockerized agent telemetry proof: skipped.",
  unknown: "Dockerized agent telemetry proof: pending.",
  not_recorded: "Dockerized agent telemetry proof: not recorded.",
};

export function buildObservabilityStatusView(observability) {
  const statusKey = String(observability?.status || "disabled").trim() || "disabled";
  const endpointHint = String(observability?.endpoint_hint || "unset").trim() || "unset";
  const liveProbe = observability?.live_collector_probe || {};
  const liveProbeResult =
    String(liveProbe?.last_probe_result || "unknown").trim() || "unknown";
  const visibilityProbe = observability?.trace_visibility_probe || {};
  const visibilityProbeResult =
    String(
      observability?.last_visibility_probe_result || visibilityProbe?.last_probe_result || "not_recorded",
    ).trim() || "not_recorded";
  const portalConfirmation = String(
    observability?.last_portal_confirmation ||
      observability?.portal_confirmation?.confirmation_state ||
      "not_recorded",
  ).trim() || "not_recorded";
  const dockerizedProbe = observability?.dockerized_agent_probe || {};
  const dockerizedProbeResult =
    String(
      observability?.dockerized_agent_probe_result ||
        dockerizedProbe?.last_probe_result ||
        "not_recorded",
    ).trim() || "not_recorded";
  const serviceName =
    String(observability?.service_name || "novali-operator-shell").trim() ||
    "novali-operator-shell";
  const shutdownResult =
    String(observability?.last_otel_shutdown_result || "unknown").trim() || "unknown";
  const shutdownTimeoutCount = Number(observability?.last_otel_shutdown_timeout_count || 0);
  const shutdownErrorType =
    String(observability?.last_otel_shutdown_error_type || "").trim() || null;
  const shutdownState = observability?.observability_shutdown || {};
  const shutdownErrorSummary =
    String(shutdownState?.last_error_summary_redacted || "").trim() || null;
  const expectedTimeoutTracebackSuppressed = Boolean(
    observability?.expected_timeout_traceback_suppressed ||
      shutdownState?.traceback_suppressed_for_expected_timeout,
  );
  const redactionMode =
    String(observability?.redaction_mode || "strict").trim() || "strict";
  const activeProtocol =
    String(observability?.active_otlp_protocol || visibilityProbe?.otlp_protocol || "unknown").trim() ||
    "unknown";
  const serviceNameLmSafe = Boolean(observability?.service_name_lm_safe);
  const serviceNameWarning =
    String(observability?.service_name_lm_warning || "").trim() || null;
  const lmMappingMissing = Array.isArray(observability?.lm_mapping_missing)
    ? observability.lm_mapping_missing
    : [];
  const lmMappingComplete = Boolean(observability?.lm_mapping_attributes_complete);
  const dockerizedProbeId =
    String(
      observability?.dockerized_agent_probe_id || dockerizedProbe?.last_probe_id || "",
    ).trim() || null;
  const dockerizedProtocol =
    String(
      observability?.dockerized_protocol || dockerizedProbe?.otlp_protocol || "unknown",
    ).trim() || "unknown";
  const dockerizedEndpointMode =
    String(
      observability?.dockerized_endpoint_mode || dockerizedProbe?.endpoint_mode || "unknown",
    ).trim() || "unknown";
  const dockerizedRuntimeProven = Boolean(
    observability?.dockerized_agent_runtime_proven || dockerizedProbe?.container_runtime_proven,
  );
  const dockerizedMappingComplete = Boolean(
    observability?.dockerized_mapping_complete ||
      dockerizedProbe?.lm_mapping_attributes_complete,
  );
  const label = STATUS_LABELS[statusKey] || STATUS_LABELS.disabled;
  let detail =
    "LogicMonitor/OTel collector evidence only; governance remains controller-owned.";
  if (statusKey === "configured") {
    detail = "Collector export is configured and waiting for the next runtime flush.";
  } else if (statusKey === "exporting") {
    detail = "Collector export is active; telemetry remains advisory evidence only.";
  } else if (statusKey === "degraded") {
    detail = "Collector export is degraded or unreachable; NOVALI runtime behavior is unchanged.";
  } else if (statusKey === "unavailable") {
    detail = "Observability dependencies are unavailable; NOVALI falls back to a safe no-op mode.";
  }
  if (shutdownResult === "timeout") {
    detail =
      "The latest observability shutdown recorded a bounded timeout; timeout evidence does not approve or block work by itself.";
  } else if (shutdownResult === "degraded" || shutdownResult === "failed") {
    detail =
      "The latest observability shutdown captured degraded evidence; controller authority and review gates remain unchanged.";
  } else if (shutdownResult === "unavailable") {
    detail =
      "The latest observability shutdown found the exporter path unavailable and preserved that state as evidence only.";
  }
  let liveProbeDetail =
    "Latest live collector proof state is read from safe local evidence artifacts only.";
  if (liveProbeResult === "success") {
    liveProbeDetail =
      "Latest safe proof artifact shows a clean live OTLP flush to the configured collector path.";
  } else if (liveProbeResult === "failure") {
    liveProbeDetail =
      "Latest safe proof artifact shows the live collector path failed or stayed degraded.";
  } else if (liveProbeResult === "skipped") {
    liveProbeDetail =
      "Live proof stays opt-in and was skipped for this shell snapshot.";
  }
  let visibilityProbeDetail =
    "Trace visibility proof stays separate from portal confirmation and relies on local safe evidence only.";
  if (visibilityProbeResult === "success") {
    visibilityProbeDetail =
      "Latest trace visibility probe reached a clean app-to-collector exporting state.";
  } else if (visibilityProbeResult === "failure") {
    visibilityProbeDetail =
      "Latest trace visibility probe did not reach a clean exporting state, so protocol or mapping drift is still possible.";
  } else if (visibilityProbeResult === "skipped") {
    visibilityProbeDetail =
      "Trace visibility probe was intentionally skipped, often because the selected protocol dependency was unavailable.";
  }
  let portalConfirmationDetail =
    "Portal visibility remains a manual operator evidence step unless a credential-safe API path is later approved.";
  if (portalConfirmation === "confirmed") {
    portalConfirmationDetail =
      "An operator-recorded artifact confirms the proof was visible in the LogicMonitor portal.";
  } else if (portalConfirmation === "not_confirmed") {
    portalConfirmationDetail =
      "An operator-recorded artifact says the proof is not yet visible in the LogicMonitor portal.";
  }
  let dockerizedProbeDetail =
    "Dockerized proof reads only safe local artifacts and shows whether the packaged NOVALI container reached the collector path.";
  if (dockerizedProbeResult === "success") {
    dockerizedProbeDetail =
      "The packaged NOVALI container reached a clean app-to-collector exporting state from inside Docker.";
  } else if (dockerizedProbeResult === "failure") {
    dockerizedProbeDetail =
      "The packaged NOVALI container did not reach a clean export path, so Docker topology or collector reachability still needs attention.";
  } else if (dockerizedProbeResult === "skipped") {
    dockerizedProbeDetail =
      "The Dockerized probe stays opt-in and was skipped for this shell snapshot.";
  }
  return {
    label,
    statusKey,
    serviceName,
    serviceNameLmSafe,
    serviceNameWarning,
    endpointHint,
    redactionMode,
    activeProtocol,
    detail,
    liveProbeResult,
    liveProbeLabel: PROBE_LABELS[liveProbeResult] || PROBE_LABELS.unknown,
    liveProbeDetail,
    visibilityProbeResult,
    visibilityProbeLabel:
      VISIBILITY_LABELS[visibilityProbeResult] || VISIBILITY_LABELS.not_recorded,
    visibilityProbeDetail,
    visibilityProbeId:
      String(observability?.last_visibility_probe_id || visibilityProbe?.last_probe_id || "").trim() ||
      null,
    dockerizedProbeResult,
    dockerizedProbeLabel:
      DOCKERIZED_PROBE_LABELS[dockerizedProbeResult] || DOCKERIZED_PROBE_LABELS.not_recorded,
    dockerizedProbeDetail,
    dockerizedProbeId,
    dockerizedProtocol,
    dockerizedEndpointMode,
    dockerizedRuntimeProven,
    dockerizedMappingComplete,
    portalConfirmation,
    portalConfirmationLabel:
      PORTAL_CONFIRMATION_LABELS[portalConfirmation] || PORTAL_CONFIRMATION_LABELS.not_recorded,
    portalConfirmationDetail,
    lmMappingComplete,
    lmMappingMissing,
    alertCandidates: Array.isArray(observability?.alert_candidates)
      ? observability.alert_candidates
      : [],
    policyNotes: [
      "Dockerized agent telemetry proof is evidence only.",
      "Telemetry is evidence only.",
      "Telemetry shutdown status is evidence only.",
      "Exporter timeout does not approve or block work by itself.",
      "Portal visibility remains operator-confirmed.",
      "LogicMonitor does not control NOVALI.",
      "Controller authority and review gates remain unchanged.",
      "Endpoint shown as hint only.",
    ],
    lastExportResult: String(observability?.last_export_result || "not_attempted"),
    lastErrorType: observability?.last_error_type || null,
    lastShutdownResult: shutdownResult,
    lastShutdownTimeoutCount: shutdownTimeoutCount,
    lastShutdownErrorType: shutdownErrorType,
    lastShutdownErrorSummary: shutdownErrorSummary,
    expectedTimeoutTracebackSuppressed,
  };
}
