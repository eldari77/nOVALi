# LogicMonitor Alert Readiness Pack

This folder defines alert-readiness guidance for the collector-first NOVALI observability path after rc83, rc83.1, and the rc83.2 Dockerized proof.

Boundaries:

- Telemetry is evidence only.
- LogicMonitor does not control NOVALI.
- Controller authority and review gates remain unchanged.
- No portal credentials, access IDs, access keys, bearer tokens, or Docker secrets belong in this repo.

Files:

- `rc83_alert_readiness.md`
- `alert_classes.example.yaml`
- `rc88_operator_alert_loop.md`

Current posture:

- local shell alert candidates stay bounded to exporter degradation, failed proofs, and deferred-pressure evidence
- rc88 adds a local operator alert loop with evidence-only acknowledgement/review and portal-readiness mapping docs
- no outbound email, SMS, Slack, webhook, or portal alert automation is enabled here
- portal activation and escalation remain manual/operator-owned
