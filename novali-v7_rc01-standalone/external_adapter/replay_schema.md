# rc85 Replay Packet Schema

Replay packets are operator-readable evidence artifacts for mock external-adapter actions.

Required rc85 fields:

- `schema_version=rc85.v1`
- `replay_packet_id`
- `action_id`
- `adapter_name`
- `adapter_kind`
- `source_controller`
- `governing_directive_ref`
- `action_type`
- `intended_effect`
- `preconditions_summary`
- `pre_state_snapshot_ref`
- `post_state_result`
- `status`
- `result_summary`
- `failure_reason_redacted`
- `uncertainty_reason_redacted`
- `retry_count`
- `timeout_ms`
- `rollback_candidate`
- `rollback_analysis_ref`
- `review_required`
- `review_reasons`
- `kill_switch_state`
- `telemetry_trace_hint`
- `created_at`
- `completed_at`
- `package_version=rc85`
- `branch=novali-v6`
- `review_item_id`
- `review_status`
- `rollback_analysis_id`
- `checkpoint_ref`
- `prior_stable_state_ref`
- `escalation_status`
- `escalation_reasons`
- `evidence_integrity_status`
- `restore_allowed`
- `restore_performed`

Storage:

- packet JSON files: `artifacts/operator_proof/rc85/replay_packets/`
- replay ledger JSONL: `data/external_adapter_replay.jsonl`

Compatibility:

- rc84 packets remain readable through the replay summary helpers
- rc85 adds review/rollback linkage fields without invalidating earlier proof artifacts

Redaction rules:

- no credentials
- no raw prompt bodies
- no raw chat/user content
- no OTLP headers
- no Docker env dumps
- no credential-bearing endpoint URLs
- no fake proof seeds
