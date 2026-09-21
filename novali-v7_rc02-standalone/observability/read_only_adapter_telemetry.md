# rc87 Read-Only Adapter Telemetry

rc87 adds read-only adapter telemetry on the existing rc82-rc86 observability substrate.

Boundaries:

- telemetry is evidence only
- observations are evidence only
- replay packets are evidence only
- review tickets are operator-gated evidence only
- no telemetry signal can widen authority or imply mutation permission

Primary spans:

- `novali.read_only_adapter.snapshot.load`
- `novali.read_only_adapter.schema.validate`
- `novali.read_only_adapter.integrity.validate`
- `novali.read_only_adapter.observation.summarize`
- `novali.read_only_adapter.replay_packet.write`
- `novali.read_only_adapter.review_ticket.created`
- `novali.read_only_adapter.rollback_analysis.created`
- `novali.read_only_adapter.mutation.refused`
- `novali.read_only_adapter.lane_attribution.check`
- `novali.read_only_adapter.rc87_proof.run`

Primary metrics:

- `novali.read_only_adapter.snapshot.load.count`
- `novali.read_only_adapter.snapshot.validation.count`
- `novali.read_only_adapter.integrity.failure.count`
- `novali.read_only_adapter.review_ticket.count`
- `novali.read_only_adapter.replay_packet.write.count`
- `novali.read_only_adapter.rollback_analysis.count`
- `novali.read_only_adapter.mutation.refusal.count`
- `novali.read_only_adapter.stale_snapshot.count`
- `novali.read_only_adapter.conflict.count`
- `novali.read_only_adapter.lane_attribution.failure.count`

Primary structured redacted events:

- `novali.read_only_adapter.snapshot.loaded`
- `novali.read_only_adapter.schema.validated`
- `novali.read_only_adapter.integrity.clean`
- `novali.read_only_adapter.integrity.failed`
- `novali.read_only_adapter.conflict.detected`
- `novali.read_only_adapter.stale_snapshot.detected`
- `novali.read_only_adapter.replay_packet.written`
- `novali.read_only_adapter.review_ticket.created`
- `novali.read_only_adapter.rollback_analysis.created`
- `novali.read_only_adapter.mutation.refused`
- `novali.read_only_adapter.lane_attribution.failed`
- `novali.read_only_adapter.rc87_proof.completed`

Low-cardinality attributes only:

- `novali.adapter.name`
- `novali.adapter.kind`
- `novali.adapter.mode`
- `novali.source.kind`
- `novali.environment.kind`
- `novali.validation.status`
- `novali.integrity.status`
- `novali.review_status`
- `novali.review_trigger`
- `novali.controller.lane`
- `novali.controller.role`
- `novali.result`
- `novali.proof_kind`
