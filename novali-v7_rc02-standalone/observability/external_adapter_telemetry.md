# rc85 External Adapter Telemetry

rc85 keeps mock-adapter telemetry on the existing rc82-rc83.2 observability substrate and adds review-hold, rollback-linkage, and evidence-integrity signals.

Boundaries:

- telemetry is evidence only
- replay packets are evidence only
- review items are evidence/gating only
- rollback analysis is evidence/planning only
- no telemetry signal can override controller authority or review gates

Primary spans:

- `novali.external_adapter.snapshot`
- `novali.external_adapter.action.proposed`
- `novali.external_adapter.preconditions.validate`
- `novali.external_adapter.action.review_required`
- `novali.external_adapter.action.mock_execute`
- `novali.external_adapter.action.result_acknowledged`
- `novali.external_adapter.replay_packet.write`
- `novali.external_adapter.rollback_analysis.requested`
- `novali.external_adapter.kill_switch.triggered`
- `novali.external_adapter.proof.run`
- `novali.external_adapter.review.evaluate`
- `novali.external_adapter.review.item_created`
- `novali.external_adapter.review.escalated`
- `novali.external_adapter.evidence.integrity_check`
- `novali.external_adapter.rollback.link_checkpoint`
- `novali.external_adapter.rollback.analysis_created`
- `novali.external_adapter.rollback.ambiguity_detected`
- `novali.external_adapter.review_hold.enter`
- `novali.external_adapter.review_hold.summary`
- `novali.external_adapter.rc85_proof.run`

Primary metrics:

- `novali.external_adapter.snapshot.count`
- `novali.external_adapter.action.count`
- `novali.external_adapter.action.duration_ms`
- `novali.external_adapter.action.failure.count`
- `novali.external_adapter.action.uncertain.count`
- `novali.external_adapter.review_required.count`
- `novali.external_adapter.replay_packet.write.count`
- `novali.external_adapter.rollback_analysis.count`
- `novali.external_adapter.kill_switch.count`
- `novali.external_adapter.redaction.failure.count`
- `novali.external_adapter.review_item.count`
- `novali.external_adapter.review_item.pending.count`
- `novali.external_adapter.review_item.escalated.count`
- `novali.external_adapter.evidence_missing.count`
- `novali.external_adapter.rollback.ambiguity.count`
- `novali.external_adapter.rollback.restore_allowed.count`
- `novali.external_adapter.rollback.restore_performed.count`
- `novali.external_adapter.review_hold.enter.count`
- `novali.external_adapter.integrity.failure.count`

Primary structured redacted events:

- `novali.external_adapter.snapshot`
- `novali.external_adapter.action.proposed`
- `novali.external_adapter.preconditions.failed`
- `novali.external_adapter.action.review_required`
- `novali.external_adapter.action.mock_executed`
- `novali.external_adapter.action.failed`
- `novali.external_adapter.action.uncertain`
- `novali.external_adapter.replay_packet.written`
- `novali.external_adapter.rollback_analysis.created`
- `novali.external_adapter.kill_switch.triggered`
- `novali.external_adapter.redaction_failure`
- `novali.external_adapter.review.item_created`
- `novali.external_adapter.review.escalated`
- `novali.external_adapter.review.acknowledged`
- `novali.external_adapter.review.resolved_mock_only`
- `novali.external_adapter.evidence.integrity_clean`
- `novali.external_adapter.evidence.integrity_failed`
- `novali.external_adapter.rollback.ambiguity_detected`
- `novali.external_adapter.review_hold.enter`
- `novali.external_adapter.live_mutation.refused`
