# NOVALI rc85 Observability

rc85 keeps the rc82-rc83.2 collector-first observability substrate and adds telemetry for review-hold plus rollback-evidence integration around the generic external-adapter membrane.

Boundaries:

- telemetry is evidence only
- LogicMonitor does not control NOVALI
- replay packets are evidence only
- review items are evidence/gating only
- rollback analysis is evidence/planning only
- controller authority and review/intervention gates remain unchanged
- NOVALI still starts normally with telemetry disabled
- NOVALI still starts normally with telemetry enabled and an unreachable collector

Current proof/evidence lanes:

- rc83 live collector proof: `operator_shell/scripts/rc83_logicmonitor_live_collector_smoke.py`
- rc83.1 trace-visibility proof: `operator_shell/scripts/rc83_1_logicmonitor_trace_visibility_probe.py`
- rc83.2 Dockerized runtime proof: `operator_shell/scripts/rc83_2_dockerized_agent_trace_probe.py`
- rc84 mock adapter proof: `operator_shell/scripts/rc84_external_adapter_mock_proof.py`
- rc85 review/rollback proof: `operator_shell/scripts/rc85_review_rollback_integration_proof.py`

Current status:

- rc83.2 LogicMonitor portal trace visibility remains operator-confirmed after collector config correction
- rc85 carries a sanitized packaged confirmation snapshot so clean unpacks can preserve that evidence without secrets
- rc85 adds mock-only review-hold and rollback-evidence integration around the external adapter membrane
- rc85 does not add Space Engineers behavior
- rc85 does not add live external-world mutation

Key docs:

- `observability/logicmonitor/README.md`
- `observability/logicmonitor/dockerized_agent_probe.md`
- `observability/logicmonitor/portal_verification_checklist.md`
- `observability/external_adapter_telemetry.md`
- `external_adapter/README.md`
- `external_adapter/review_hold_integration.md`
- `external_adapter/rollback_integration.md`
