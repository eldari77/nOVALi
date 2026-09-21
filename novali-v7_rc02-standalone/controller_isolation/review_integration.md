# rc86 Review Integration

rc86 reuses the existing operator review/intervention surfaces instead of creating a second governance engine.

When a high or critical identity-bleed finding is recorded, rc86 writes:

- a controller-isolation review ticket
- a controller-isolation replay/evidence packet
- bounded lane-local ledger entries

Those records are then projected into operator-state as `controller_isolation` and into the existing intervention summary as evidence only.

Important limits:

- review tickets are operator-gated evidence only
- no review ticket can approve a real external action
- no review ticket changes backend blocked/resumable/completed truth by itself
- no review ticket creates a second authority path
