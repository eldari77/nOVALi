# NOVALI rc85 Redaction Policy

rc85 keeps strict redaction by default and extends the proof posture to review items, replay packets, replay ledgers, rollback-analysis artifacts, evidence-integrity summaries, and mock adapter summaries.

Never emit:

- raw prompts or raw chat
- raw directives or trusted-source responses
- auth headers, cookies, OTLP header values, or credential-bearing endpoint URLs
- LogicMonitor access IDs, access keys, bearer tokens, portal tokens, or Docker env dumps
- raw external payload secrets

Sensitive key patterns include:

- `authorization`
- `bearer`
- `token`
- `api_key`
- `apikey`
- `access_key`
- `access_id`
- `secret`
- `password`
- `credential`
- `cookie`
- `set-cookie`
- `session_secret`
- `provider_key`
- `trusted_source_credential`
- `novali.secret`
- `http.request.header.authorization`
- `request.header.authorization`
- `otel_exporter_otlp_headers`
- `logicmonitor_access_id`
- `logicmonitor_access_key`
- `lm_access_id`
- `lm_access_key`

Sensitive value patterns include:

- bearer-like values
- token-like long strings
- cookie-like values
- auth-header-like `key=value` strings
- fake proof seeds from rc83, rc83.1, rc83.2, rc84, and rc85

rc85 proof expectations:

- fake seeds must be absent from review items, replay packets, replay ledgers, rollback analyses, evidence-integrity summaries, proof summaries, shell status, docs output, package manifests, and final zips
- replay packets, review items, rollback-analysis artifacts, and evidence-integrity summaries are redacted before write
- fake proof seeds must be constructed at runtime rather than stored as raw literals in packaged source
- shell/API status shows only bounded operational state, never raw secret material
