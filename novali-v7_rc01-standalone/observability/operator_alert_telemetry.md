# rc88 / rc88.1 Operator Alert Telemetry

Resource identity:

- `service.version=novali-v6_rc88_1`
- `novali.package.version=rc88_1`
- `novali.telemetry.schema_version=rc88_1.v1`

Spans:

- `novali.operator_alert.raise`
- `novali.operator_alert.evidence_bundle.create`
- `novali.operator_alert.lifecycle.acknowledge`
- `novali.operator_alert.lifecycle.review`
- `novali.operator_alert.lifecycle.close_evidence_only`
- `novali.operator_alert.lifecycle.supersede`
- `novali.operator_alert.read_only.map`
- `novali.operator_alert.telemetry_candidate.evaluate`
- `novali.operator_alert.admission_criteria.evaluate`
- `novali.operator_alert.rc88_proof.run`
- `novali.operator_alert.rc88_1_proof.run`

Metrics:

- `novali.operator_alert.count`
- `novali.operator_alert.raised.count`
- `novali.operator_alert.acknowledged.count`
- `novali.operator_alert.reviewed.count`
- `novali.operator_alert.blocked.count`
- `novali.operator_alert.critical.count`
- `novali.operator_alert.evidence_bundle.count`
- `novali.operator_alert.read_only.count`
- `novali.operator_alert.telemetry_candidate.count`
- `novali.operator_alert.admission_assessment.count`
- `novali.operator_alert.telemetry_shutdown.count`

Structured redacted events:

- `novali.operator_alert.raised`
- `novali.operator_alert.evidence_bundle.created`
- `novali.operator_alert.acknowledged`
- `novali.operator_alert.reviewed`
- `novali.operator_alert.closed_evidence_only`
- `novali.operator_alert.superseded`
- `novali.operator_alert.read_only_mapped`
- `novali.operator_alert.admission_assessed`
- `novali.operator_alert.rc88_proof.completed`
- `novali.operator_alert.rc88_1_proof.completed`

Allowed low-cardinality attributes:

- `novali.branch`
- `novali.package.version`
- `novali.runtime.role`
- `novali.alert.type`
- `novali.alert.severity`
- `novali.alert.status`
- `novali.alert.source`
- `novali.adapter.kind`
- `novali.adapter.mode`
- `novali.controller.lane`
- `novali.controller.role`
- `novali.review_status`
- `novali.result`
- `novali.proof_kind`

Boundaries:

- telemetry is evidence only
- no LogicMonitor API integration is added in rc88
- raw notes, raw payloads, raw prompts, credentials, headers, Docker env, and unbounded IDs are excluded

rc88.1 additions:

- telemetry shutdown timeout, exporter unavailable, and unexpected shutdown exception alerts are mapped as local evidence only
- expected shutdown timeouts stay visible as bounded evidence without noisy unhandled traceback output
