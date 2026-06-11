# rc88.1 Telemetry Shutdown Handling

rc88.1 centralizes NOVALI observability flush and shutdown handling so deterministic proofs stay quiet without hiding real failures.

Public helpers:

- `flush_observability(timeout_ms=None, reason=None)`
- `shutdown_observability(timeout_ms=None, reason=None)`
- `get_observability_shutdown_status()`

Shutdown result classes:

- `success`
- `disabled`
- `unavailable`
- `timeout`
- `degraded`
- `failed`

Behavior:

- telemetry disabled remains a quiet no-op
- missing SDK/exporter remains `unavailable` without traceback noise
- collector-unreachable or expected exporter timeout remains bounded evidence as `timeout`
- unexpected exceptions remain visible as redacted `degraded` or `failed` evidence
- shutdown is idempotent and bounded
- telemetry shutdown status is evidence only

Configuration:

- `NOVALI_OTEL_SHUTDOWN_TIMEOUT_MS`
  - default: `3000`
  - invalid values fall back safely
  - long timeouts are not the default

Operator-facing status fields:

- `last_otel_shutdown_result`
- `last_otel_shutdown_timeout_count`
- `last_otel_shutdown_error_type`
- `expected_timeout_traceback_suppressed`
- `observability_shutdown`

Boundaries:

- expected telemetry shutdown timeouts are recorded as evidence, not hidden
- unexpected telemetry errors remain visible as redacted degraded/failure evidence
- no raw stack traces are exposed through operator state
- no endpoint headers or credentials are exposed
- LogicMonitor remains observability tooling only
- no LogicMonitor API alert creation is added
