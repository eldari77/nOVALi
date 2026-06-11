# rc88 Evidence Bundles

Primary record:

- `OperatorAlertEvidenceBundle`
- `schema_version=rc88.v1`

Fields:

- `evidence_bundle_id`
- `alert_id`
- `source`
- `source_case`
- `replay_packet_refs`
- `review_ticket_refs`
- `rollback_analysis_refs`
- `mutation_refusal_refs`
- `source_immutability_refs`
- `lane_attribution_refs`
- `telemetry_refs`
- `status_endpoint_snapshot_ref`
- `package_validation_refs`
- `evidence_integrity_status`
- `evidence_integrity_findings`
- `redaction_status`

Storage:

- `artifacts/operator_proof/rc88/evidence_bundles/*.json`
- `artifacts/operator_proof/rc88/evidence_bundle_summary.json`

Integrity behavior:

- linked refs must exist where they are claimed
- missing replay or other required evidence must fail closed
- missing optional evidence should be omitted, not fabricated
- secret-like content in references fails redaction/integrity
- path hints stay bounded and redacted

Evidence bundle rules:

- use path hints, not credential-bearing absolute paths
- do not embed raw fixture payloads, prompts, private content, credentials, endpoint headers, or Docker env
- integrity failures raise or update alert evidence instead of silently passing
