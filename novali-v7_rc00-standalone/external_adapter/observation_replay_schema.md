# rc87 Observation Replay Schema

rc87 writes read-only observation replay packets as evidence artifacts.

Schema:

- `schema_version=rc87.v1`
- `replay_kind=read_only_observation`
- `adapter_name`
- `adapter_kind=read_only_fixture`
- `source_kind=static_fixture`
- `source_ref_hint`
- `snapshot_id`
- `lane_id`
- `source_controller`
- `governing_directive_ref`
- `observation_summary_redacted`
- `entity_count`
- `relationship_count`
- `metric_count`
- `validation_status`
- `integrity_status`
- `review_required`
- `review_reasons`
- `review_ticket_id`
- `rollback_analysis_id`
- `prior_snapshot_ref`
- `checkpoint_ref`
- `mutation_refused`
- `mutation_refusal_id`
- `telemetry_trace_hint`
- `created_at`
- `package_version=rc87`
- `branch=novali-v6`

Storage:

- packet JSON: `artifacts/operator_proof/rc87/observation_replay_packets/`
- ledger JSONL: `data/read_only_adapter_observation_replay.jsonl`

Rules:

- no raw fixture dump
- no secrets
- no credential-bearing URLs
- no hidden mutation side effects
- replay packets are evidence only
