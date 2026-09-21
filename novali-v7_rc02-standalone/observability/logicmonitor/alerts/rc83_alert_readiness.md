# rc83 / rc83.1 / rc83.2 Alert Readiness

rc83 established the alert classes. rc83.1 adds trace-visibility and portal-confirmation alignment, and rc83.2 adds Dockerized agent proof evidence without changing controller authority.

Implemented locally:

- `collector_down`
  - purpose: flag that the latest live collector proof failed
  - evidence source: `artifacts/operator_proof/rc83/logicmonitor_live_collector_smoke_summary.json`
  - suggested threshold: any latest failure after explicit proof run
  - severity: warning
  - implementation state: implemented

- `telemetry_export_failure`
  - purpose: surface exporter degraded or unreachable state
  - evidence source: shell observability status and exporter failure counter
  - suggested threshold: any sustained non-zero increase
  - severity: warning
  - implementation state: implemented

- `no_telemetry_seen`
  - purpose: surface host or Dockerized trace-visibility proof failure
  - evidence source: `artifacts/operator_proof/rc83_1/trace_visibility_probe_summary.json` or `artifacts/operator_proof/rc83_2/dockerized_agent_trace_probe_summary.json`
  - suggested threshold: any latest `result=failure` after explicit proof run
  - severity: warning
  - implementation state: implemented

- `deferred_pressure_high`
  - purpose: keep shell-visible deferred backlog pressure reviewable
  - evidence source: shell runtime proxy counts and local alert candidates
  - suggested threshold: repeated high-band manager checks
  - severity: warning
  - implementation state: implemented

Defined for operator portal follow-through:

- `checkpoint_failure`
- `review_hold_active`
- `repeated_review_hold`
- `deferred_pressure_worsening`
- `manager_check_stalled`
- `queue_pressure_saturation`
- `redaction_failure`
- `rollback_loop_candidate`

For defined-only or portal-required classes:

- evidence should come from shell status, proof artifacts, controller/checkpoint artifacts, and collector dashboards
- thresholds remain operator-tuned after confirming normal baseline traffic
- portal escalation chains remain manual/operator-owned
