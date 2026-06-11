# rc88 / rc88.1 Operator Alerts

rc88 adds a local operator alert loop around read-only adapter evidence and existing bounded runtime evidence.
rc88.1 keeps that local alert loop evidence-only while hardening telemetry shutdown and exporter-degradation alert mapping.

Boundaries:

- alerts are evidence signals, not authority
- acknowledgement is not approval
- review is not approval
- no real external-world mutation
- no Space Engineers behavior is active
- LogicMonitor remains observability tooling only
- controller authority and review gates remain unchanged
- telemetry shutdown status is evidence only
- expected exporter timeouts remain bounded evidence, not silent success

Implementation:

- module: `operator_shell/operator_alerts/`
- proof runner: `operator_shell/scripts/rc88_operator_alert_loop_proof.py`
- cleanup proof runner: `operator_shell/scripts/rc88_1_telemetry_shutdown_cleanup_proof.py`
- local data store: `data/operator_alerts/`
- proof artifacts: `artifacts/operator_proof/rc88/`
- cleanup artifacts: `artifacts/operator_proof/rc88_1/`

rc88 alert sources:

- rc87 read-only adapter validation, replay, rollback, mutation-refusal, lane-attribution, and source-immutability evidence
- rc85 review-hold / rollback evidence
- rc86 controller-isolation findings
- bounded runtime observability and local shell state
- rc88.1 telemetry shutdown timeout, exporter degradation, exporter unavailability, and unexpected shutdown exception evidence

Local lifecycle actions:

- `acknowledge`
- `mark reviewed`
- `close evidence-only`
- `supersede`

Those actions record local lifecycle evidence only. They do not approve execution, mutation, or governance expansion.

rc88.1 transition note:

- rc88.1 is the proposed final v6 cleanup patch before closeout
- v7rc00 setup remains planning-only in rc88.1
- no v7 branch or package is created here
