# v7rc00 Operator Handoff

This handoff marks the version boundary from frozen `novali-v6 rc88.1` to active `novali-v7 v7rc00`.

Operator-facing summary:

- v6 is preserved as historical reference
- v7rc00 is the clean active baseline
- active physical source root is `novali-v7`
- behavior is intentionally unchanged except for version/package/docs/proof identity
- Space Engineers remains inactive
- the earlier `novali-v6/dist/novali-v7_rc00*` package is superseded by the topology-correct package built from `novali-v7`

Workspace / git note:

- the enclosing git worktree remained broader than the repo root and dirty, so no destructive in-place git branch surgery was attempted
- the topology correction instead materialized a sibling `novali-v7` source directory and re-established active package truth from there
- active line identity is therefore recorded through source-of-truth docs, runtime identity, package identity, and proof artifacts rather than an enforced local git branch rename

Next step:

- choose the first v7 planning decision after v7rc00 acceptance
- the only SE-related candidate allowed next is planning-only, and only if the operator explicitly approves it
