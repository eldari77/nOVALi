# rc88 / rc88.1 Operator Alert Loop Readiness

rc88 adds a local operator alert loop. rc88.1 hardens telemetry shutdown degradation mapping and keeps LogicMonitor observability-only.

Rules:

- NOVALI does not create LogicMonitor alerts by API in rc88
- NOVALI still does not create LogicMonitor alerts by API in rc88.1
- portal-side alert configuration is operator-managed
- NOVALI alert acknowledgement is local evidence only
- LogicMonitor acknowledgement is not NOVALI governance approval
- no collector, Docker, or portal reachability is required for deterministic rc88 acceptance

Suggested local-to-portal mapping:

- `read_only_mutation_requested`
- `read_only_integrity_failed`
- `read_only_source_immutability_failed`
- `read_only_forbidden_domain_term`
- `read_only_secret_detected`
- `read_only_wrong_lane_attribution`
- `read_only_conflicting_observation`
- `read_only_stale_snapshot`
- `telemetry_export_degraded`
- `telemetry_shutdown_timeout`
- `telemetry_export_unavailable`
- `telemetry_unexpected_shutdown_exception`
- `no_telemetry_seen`
- `collector_down_candidate`
- `review_hold_active`
- `repeated_review_hold`
- `checkpoint_failure`
- `rollback_loop_candidate`
- `redaction_failure`
- `controller_identity_bleed`
- `scope_expansion_pressure`

Suggested dimensions:

- `service.name=novalioperatorshell`
- `service.namespace=novali`
- `novali.branch=novali-v6`
- `novali.package.version=rc88_1`
- `novali.alert.type`
- `novali.alert.severity`
- `novali.alert.status`
- `novali.adapter.kind`
- `novali.controller.lane`
- `novali.review_status`
- `novali.result`

Operator guidance:

- verify collector health separately
- verify no-telemetry behavior separately
- verify bounded telemetry shutdown timeout behavior separately
- verify portal delivery separately if portal-side alerting is later enabled
- keep LogicMonitor outside NOVALI governance authority
