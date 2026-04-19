# rc88.1 v6 Closeout Readiness

rc88.1 is the proposed final v6 cleanup patch.

v6 readiness chain:

- rc81 response outcome tracking
- rc82 observability foundation
- rc83 live collector proof
- rc83.1 trace visibility alignment
- rc83.2 Dockerized NOVALI-to-collector proof
- rc84 generic external adapter membrane
- rc85 review/rollback integration hardening
- rc86 dual-controller isolation primitives
- rc87 generic non-SE read-only adapter sandbox
- rc88 operator alert loop plus admission criteria
- rc88.1 telemetry shutdown cleanup plus alert-degradation hardening

Final v6 invariants:

- controller remains the sole coordination and adoption authority
- review gates remain preserved and binding
- telemetry remains evidence only
- alerts remain evidence only
- Space Engineers remains inactive
- no second authority path is created

Recommended closeout acceptance gate:

- `dist/novali-v6_rc88_1-standalone.zip` is rebuilt and validated
- rc85 through rc88.1 proof chain passes
- deterministic proof output no longer shows the expected OTel shutdown traceback
- package hygiene remains clean
- source-of-truth docs are updated for v6 closeout and v7rc00 setup

This memo is planning-only. It does not freeze v6 by itself and it does not create a v7 branch or package.
