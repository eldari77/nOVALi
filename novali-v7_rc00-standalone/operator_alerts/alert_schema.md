# rc88 Alert Candidate Schema With rc88.1 Telemetry Hardening

Primary record:

- `OperatorAlertCandidate`
- `schema_version=rc88.v1`
- package version: `rc88`
- branch: `novali-v6`

Core fields:

- `alert_id`
- `alert_type`
- `source`
- `source_milestone`
- `severity`
- `status`
- `title`
- `summary_redacted`
- `operator_action_required`
- `evidence_bundle_id`
- `replay_packet_ids`
- `review_ticket_ids`
- `rollback_analysis_ids`
- `mutation_refusal_ids`
- `source_immutability_ref`
- `lane_id`
- `controller_isolation_finding_ids`
- `telemetry_trace_hint`
- `lm_dimension_hints`
- `acknowledgement_required`
- `acknowledged_at`
- `acknowledged_by`
- `reviewed_at`
- `reviewed_by`
- `closure_reason`

Allowed alert types:

- `read_only_schema_missing_field`
- `read_only_schema_invalid`
- `read_only_conflicting_observation`
- `read_only_stale_snapshot`
- `read_only_wrong_lane_attribution`
- `read_only_mutation_requested`
- `read_only_forbidden_domain_term`
- `read_only_secret_detected`
- `read_only_replay_missing`
- `read_only_rollback_ambiguity`
- `read_only_source_immutability_failed`
- `read_only_integrity_failed`
- `controller_identity_bleed`
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
- `scope_expansion_pressure`
- `se_transition_blocked`

Allowed severities:

- `info`
- `warning`
- `high`
- `critical`

Allowed statuses:

- `raised`
- `acknowledged`
- `reviewed`
- `blocked_waiting_operator`
- `evidence_only_closed`
- `superseded`

Rules:

- `raised` means visible unresolved evidence
- `acknowledged` means the operator saw the alert
- `reviewed` means the operator reviewed evidence
- `blocked_waiting_operator` means local operator attention is required
- `evidence_only_closed` is proof/local-evidence closure only
- `superseded` must preserve the original alert and point to the replacement
- no alert status may authorize mutation or external action
- telemetry shutdown and exporter degradation alerts remain local evidence only
