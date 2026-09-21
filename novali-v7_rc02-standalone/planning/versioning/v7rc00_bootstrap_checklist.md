# v7rc00 Bootstrap Checklist

v7rc00 should start only after rc88.1 is accepted as the canonical v6 package.

Baseline:

- start from `dist/novali-v6_rc88_1-standalone.zip`
- preserve all v6 governance invariants
- preserve package-truth discipline
- preserve evidence-only telemetry and alerts
- preserve the non-secret LogicMonitor confirmation snapshot
- preserve read-only adapter, admission, and controller-isolation evidence
- preserve identity-lane inactive/mock-only posture

Naming targets for the later bootstrap step:

- branch: `novali-v7`
- package: `dist/novali-v7_rc00-standalone.zip`

v7rc00 should include:

- clean source-of-truth docs
- migrated ledger snapshot
- frozen v6 closeout reference
- route and startup validation
- package hygiene
- no behavior-changing code unless necessary for version identity or closeout carry-forward

Explicit non-goals for rc88.1:

- do not create the `novali-v7` branch
- do not build `dist/novali-v7_rc00-standalone.zip`
- do not begin Space Engineers implementation

Space Engineers-specific work may begin only after a separate operator-approved v7 planning prompt.
