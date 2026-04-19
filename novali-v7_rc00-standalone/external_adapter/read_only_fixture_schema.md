# rc87 Read-Only Fixture Schema

rc87 uses a neutral non-SE sandbox fixture domain under `fixtures/read_only_world/`.

Fixture set:

- `generic_world_snapshot_valid.json`
- `generic_world_snapshot_missing_fields.json`
- `generic_world_snapshot_conflict.json`
- `generic_world_snapshot_stale.json`
- `generic_world_snapshot_mutation_request.json`

Snapshot rules:

- `schema_version=rc87.v1`
- `source_kind=static_fixture`
- `read_only=true`
- `mutation_allowed=false`
- `environment_kind=generic_non_se_sandbox`
- `lane_id` must reference a known rc86 lane
- fixture content must remain redacted and non-secret

Required top-level fields:

- `schema_version`
- `source_kind`
- `source_name`
- `source_ref`
- `snapshot_id`
- `snapshot_created_at`
- `observed_at`
- `read_only`
- `environment_kind`
- `lane_id`
- `observed_entities`
- `observed_relationships`
- `observed_metrics`
- `integrity_markers`
- `mutation_allowed`
- `notes_redacted`
- `package_version=rc87`
- `branch=novali-v6`

Observed entity fields:

- `entity_id`
- `entity_type`
- `label_redacted`
- `state`
- `location_hint_redacted`
- `attributes_redacted`
- `observed_at`

Forbidden fixture content:

- Space Engineers terms
- player names
- server names
- live credentials
- endpoint URLs with secrets
- raw private/user content
- mutation commands
