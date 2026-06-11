# rc86 Lane Schema

rc86 defines exactly three identity lanes:

- `lane_director`
- `lane_sovereign_good`
- `lane_sovereign_dark`

Each lane is a JSON-serializable `ControllerLaneIdentity` record with:

- `schema_version=rc86.v1`
- stable `lane_id` and `lane_role`
- `active=false` by default
- `mode=mock_only`
- `authority_level=evidence_namespace`
- `adoption_authority=false`
- `coordination_authority=false`
- `can_execute_external_actions=false`
- per-lane doctrine, memory, summary, intervention, replay, review, and telemetry namespaces

Guardrails:

- identity lanes do not create new adoption authority
- identity lanes do not create new coordination authority
- identity lanes are evidence namespaces only
- sovereign lanes are not Space Engineers factions in rc86
