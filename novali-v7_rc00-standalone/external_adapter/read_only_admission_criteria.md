# rc88 Read-Only Adapter Admission Criteria

Purpose:

- define gates for future read-only adapters
- do not approve implementation by themselves
- do not widen authority

Required criteria:

- adapter is read-only by construction
- mutation methods are absent or fail closed
- no outbound network unless separately approved
- credential handling plan exists if a future connector would need credentials
- no credentials in artifacts
- schema validation is required
- observation integrity validation is required
- source auditability or source immutability proof is required
- replay packets are required
- review tickets are required for bad observations
- rollback/recovery evidence is required
- lane attribution is required
- wrong-lane detection is required
- identity-bleed checks are required
- telemetry dimensions are defined
- redaction proof is required
- package hygiene is required
- fresh-unpack proof is required
- operator alert loop integration is required
- LogicMonitor mapping is optional and evidence-only
- no Space Engineers behavior unless separately approved

Allowed admission statuses:

- `not_assessed`
- `blocked`
- `provisionally_admissible_for_planning`
- `admissible_for_read_only_sandbox`
- `rejected`

rc88 assessments:

- current `StaticFixtureReadOnlyAdapter`: `admissible_for_read_only_sandbox`
- hypothetical Space Engineers read-only bridge: `blocked`

Boundaries:

- admission criteria are gates, not implementation approval
- Space Engineers implementation remains blocked in rc88
- planning-only eligibility still requires explicit later operator approval
