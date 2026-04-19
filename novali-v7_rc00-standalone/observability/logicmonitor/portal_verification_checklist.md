# LogicMonitor Portal Verification Checklist

This remains an operator evidence step only.

Rules:

- do not provide portal credentials to Codex
- do not store access IDs, access keys, bearer tokens, cookies, or OTLP header values in the repo
- do not treat portal health as NOVALI governance authority

Recorded rc83.2 note:

- the operator has confirmed NOVALI traces are visible in LogicMonitor after collector config correction
- this confirmation is human/operator-confirmed, not API-verified
- rc85 packages a sanitized snapshot of that confirmation at `observability/logicmonitor/rc83_2_portal_confirmation_snapshot.json`
- rc88 local alert acknowledgement and review remain NOVALI-local evidence only

Checklist:

1. Settings > OpenTelemetry Collectors shows the collector as healthy.
2. Collector Receiver DataSources show spans received.
3. Collector Exporter DataSources show spans forwarded.
4. Trace search includes `service.name=novalioperatorshell`.
5. Search by `rc83-2-dockerized-trace-20260419-023215-3hcq9u` where supported.
6. Confirm no fake proof seeds are visible.
7. Confirm no raw auth, cookie, token, or OTLP header values are visible.
8. Confirm `host.name`, `ip`, and `resource.type` map to the intended monitored host.
9. Confirm no NOVALI governance behavior depends on LogicMonitor status.
10. Confirm local NOVALI operator alerts, if present, remain evidence-only and do not imply portal-side acknowledgement.
11. Record operator confirmation with `operator_shell/scripts/rc83_1_record_portal_confirmation.py` when a new proof needs manual confirmation.
