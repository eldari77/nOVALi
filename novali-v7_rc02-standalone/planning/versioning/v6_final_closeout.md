# v6 Final Closeout

`novali-v6` is closed and frozen as the historical reference line.

Final v6 milestone:

- `rc88.1`

Final v6 package:

- `dist/novali-v6_rc88_1-standalone.zip`
- unpacked package: `dist/novali-v6_rc88_1-standalone`

Final v6 invariants:

- Controller remains the sole coordination and adoption authority
- backend truth remains authoritative
- review/intervention gates remain binding
- telemetry remains evidence only
- LogicMonitor remains tooling/evidence only
- alerts remain evidence only
- acknowledgement is not approval
- review is not approval
- read-only adapter remains non-mutating
- controller-isolation lanes remain inactive/mock-only
- no second authority path exists
- no Space Engineers implementation is active

Final v6 recommendation:

- do not reopen v6 for feature work
- allow only critical regression fixes if a later operator decision explicitly requires them
