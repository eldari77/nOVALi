# rc86 Namespace Isolation

rc86 persists lane-local artifacts under `data/controller_isolation/`.

Expected shape:

- `data/controller_isolation/lane_registry.json`
- `data/controller_isolation/lane_director/*`
- `data/controller_isolation/lane_sovereign_good/*`
- `data/controller_isolation/lane_sovereign_dark/*`

Each lane keeps separate:

- doctrine
- memory
- summaries
- intervention history
- replay/review ledger
- review ledger

Rules:

- no shared doctrine path
- no shared memory path
- no shared summary path
- no shared intervention history path
- no shared replay/review ledger
- no hidden shared scratchpad

If any of those conditions are violated, rc86 records an identity-bleed finding and routes operator-visible review evidence through the existing review surface.
