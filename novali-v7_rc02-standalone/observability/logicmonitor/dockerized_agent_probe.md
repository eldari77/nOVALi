# rc83.2 Dockerized NOVALI Agent Trace Probe

rc83.2 remains the Dockerized LogicMonitor trace-proof milestone that precedes rc84.

Recorded outcome:

- proof id: `rc83-2-dockerized-trace-20260419-023215-3hcq9u`
- service name: `novalioperatorshell`
- endpoint mode: `host_gateway`
- protocol: `grpc`
- app-to-collector result: `success`
- exporter crashed: `false`
- container runtime proven: `true`
- redaction proof passed: `true`
- no secrets captured: `true`
- portal visibility: operator-confirmed after collector config correction

Rules:

- telemetry is evidence only
- LogicMonitor does not control NOVALI
- controller authority and review gates remain unchanged
- do not provide portal credentials, access IDs, access keys, bearer tokens, cookies, or OTLP header values to Codex

Key commands:

- host proof: `python operator_shell/scripts/rc83_1_logicmonitor_trace_visibility_probe.py`
- Dockerized proof: `python operator_shell/scripts/rc83_2_dockerized_agent_trace_probe.py`
- portal confirmation recording: `python operator_shell/scripts/rc83_1_record_portal_confirmation.py`

Important note:

- rc85 carries a sanitized packaged snapshot of the rc83.2 operator confirmation so clean handoffs can preserve that trace-visibility proof without secrets.
- rc85 builds on this confirmed proof chain, but the external adapter remains mock/no-op only and does not add live external-world mutation.
