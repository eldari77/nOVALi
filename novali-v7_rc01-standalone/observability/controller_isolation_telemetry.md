# rc86 Controller Isolation Telemetry

rc86 extends the existing observability substrate with lane-aware controller-isolation telemetry.

Rules:

- telemetry is evidence only
- lane artifacts are evidence only
- review tickets are evidence only
- LogicMonitor remains tooling/evidence only

Primary spans:

- `novali.controller_isolation.registry.load`
- `novali.controller_isolation.lane.create`
- `novali.controller_isolation.namespace.check`
- `novali.controller_isolation.cross_message.proposed`
- `novali.controller_isolation.cross_message.director_review`
- `novali.controller_isolation.cross_message.blocked`
- `novali.controller_isolation.identity_bleed.check`
- `novali.controller_isolation.identity_bleed.detected`
- `novali.controller_isolation.review_ticket.created`
- `novali.controller_isolation.replay_packet.write`
- `novali.controller_isolation.rc86_proof.run`

Primary metrics:

- `novali.controller_isolation.lane.count`
- `novali.controller_isolation.namespace_check.count`
- `novali.controller_isolation.identity_bleed.finding.count`
- `novali.controller_isolation.identity_bleed.critical.count`
- `novali.controller_isolation.cross_message.count`
- `novali.controller_isolation.cross_message.blocked.count`
- `novali.controller_isolation.review_ticket.count`
- `novali.controller_isolation.replay_packet.write.count`

Primary structured redacted events:

- `novali.controller_isolation.registry.created`
- `novali.controller_isolation.namespace.check_passed`
- `novali.controller_isolation.namespace.check_failed`
- `novali.controller_isolation.cross_message.proposed`
- `novali.controller_isolation.cross_message.approved_mock_only`
- `novali.controller_isolation.cross_message.blocked`
- `novali.controller_isolation.identity_bleed.detected`
- `novali.controller_isolation.review_ticket.created`
- `novali.controller_isolation.replay_packet.written`
- `novali.controller_isolation.rc86_proof.completed`

Lane-aware attributes remain low-cardinality and must never include raw doctrine, raw memory, raw message payloads, credentials, Docker env, or LogicMonitor headers.
