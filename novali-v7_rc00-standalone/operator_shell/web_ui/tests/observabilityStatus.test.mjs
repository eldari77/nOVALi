import test from "node:test";
import assert from "node:assert/strict";

import { buildObservabilityStatusView } from "../src/lib/observabilityStatus.js";

test("buildObservabilityStatusView maps disabled state safely", () => {
  const view = buildObservabilityStatusView(null);
  assert.equal(view.label, "Disabled");
  assert.equal(view.endpointHint, "unset");
  assert.equal(view.redactionMode, "strict");
});

test("buildObservabilityStatusView maps configured and degraded states", () => {
  const configured = buildObservabilityStatusView({
    status: "configured",
    endpoint_hint: "localhost",
    service_name: "novali-operator-shell",
    service_name_lm_safe: false,
    service_name_lm_warning:
      "Service name contains characters that may be unsafe for LogicMonitor trace display.",
    redaction_mode: "strict",
    active_otlp_protocol: "http",
    lm_mapping_attributes_complete: false,
    lm_mapping_missing: ["host.name", "ip"],
    last_visibility_probe_result: "not_recorded",
    dockerized_agent_probe_result: "skipped",
    dockerized_protocol: "grpc",
    dockerized_endpoint_mode: "host_gateway",
    dockerized_agent_runtime_proven: false,
    dockerized_mapping_complete: false,
    last_portal_confirmation: "not_recorded",
    live_collector_probe: {
      last_probe_result: "skipped",
    },
  });
  assert.equal(configured.label, "Configured");
  assert.match(configured.detail, /configured/i);
  assert.equal(configured.liveProbeLabel, "Live collector probe skipped");
  assert.equal(configured.visibilityProbeLabel, "Trace visibility probe not recorded");
  assert.equal(configured.dockerizedProbeLabel, "Dockerized agent telemetry proof: skipped.");
  assert.equal(configured.dockerizedProtocol, "grpc");
  assert.equal(configured.dockerizedEndpointMode, "host_gateway");
  assert.equal(configured.portalConfirmationLabel, "Portal visibility not recorded");
  assert.equal(configured.activeProtocol, "http");
  assert.equal(configured.serviceNameLmSafe, false);
  assert.deepEqual(configured.lmMappingMissing, ["host.name", "ip"]);
  assert.equal(configured.policyNotes.length, 8);

  const degraded = buildObservabilityStatusView({
    status: "degraded",
    endpoint_hint: "custom",
    service_name: "novali-operator-shell",
    service_name_lm_safe: true,
    redaction_mode: "standard",
    active_otlp_protocol: "grpc",
    lm_mapping_attributes_complete: true,
    last_visibility_probe_result: "failure",
    last_visibility_probe_id: "probe-123",
    dockerized_agent_probe_result: "success",
    dockerized_agent_probe_id: "docker-proof-123",
    dockerized_protocol: "grpc",
    dockerized_endpoint_mode: "host_gateway",
    dockerized_agent_runtime_proven: true,
    dockerized_mapping_complete: true,
    last_portal_confirmation: "not_confirmed",
    live_collector_probe: {
      last_probe_result: "failure",
    },
    alert_candidates: [
      {
        alert_key: "collector_down",
        label: "Live collector proof failed",
      },
    ],
    last_otel_shutdown_result: "timeout",
    last_otel_shutdown_timeout_count: 2,
    last_otel_shutdown_error_type: "ExporterTimeoutWarning",
    observability_shutdown: {
      last_error_summary_redacted: "bounded timeout evidence",
      traceback_suppressed_for_expected_timeout: true,
    },
    expected_timeout_traceback_suppressed: true,
  });
  assert.equal(degraded.label, "Collector unreachable");
  assert.equal(degraded.redactionMode, "standard");
  assert.match(degraded.detail, /shutdown recorded a bounded timeout/i);
  assert.equal(degraded.liveProbeLabel, "Live collector probe failed");
  assert.equal(degraded.visibilityProbeLabel, "Trace visibility probe failed");
  assert.equal(degraded.dockerizedProbeLabel, "Dockerized agent telemetry proof: succeeded.");
  assert.equal(degraded.dockerizedProbeId, "docker-proof-123");
  assert.equal(degraded.dockerizedRuntimeProven, true);
  assert.equal(degraded.portalConfirmationLabel, "Portal visibility not confirmed");
  assert.equal(degraded.visibilityProbeId, "probe-123");
  assert.equal(degraded.alertCandidates.length, 1);
  assert.equal(degraded.lastShutdownResult, "timeout");
  assert.equal(degraded.lastShutdownTimeoutCount, 2);
  assert.equal(degraded.lastShutdownErrorType, "ExporterTimeoutWarning");
  assert.equal(degraded.expectedTimeoutTracebackSuppressed, true);
});
