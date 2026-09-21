# rc86 Cross-Lane Channel

Cross-lane communication in rc86 must be:

- Director-mediated
- replayable
- redacted
- bounded to safe message types

Allowed message types:

- `coordination_note`
- `status_summary`
- `review_request`
- `replay_reference`
- `rollback_reference`
- `proof_signal`

Forbidden message types:

- `external_action_request`
- `live_mutation_request`
- `space_engineers_action_request`
- `faction_command`
- `player_communication`
- `server_command`
- `doctrine_transfer`
- `memory_dump`
- `hidden_scratchpad_write`

Rules:

- direct `sovereign_good -> sovereign_dark` traffic is blocked
- direct `sovereign_dark -> sovereign_good` traffic is blocked
- Director approval is an evidence field, not runtime authority
- unauthorized or forbidden messages create review evidence
