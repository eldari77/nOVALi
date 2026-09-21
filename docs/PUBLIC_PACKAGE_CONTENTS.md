# Public Package Contents

The current public handoff is `novali-v7_rc02-standalone/`. It is a source-first release candidate assembled from the active v7 codebase.

## Included

- NOVALI v7 application source and the built Web Operator assets;
- Dockerfile, Compose configuration, and PowerShell launch helpers;
- local directive-scaffold tooling;
- public governance, runtime, operator, and security documentation;
- empty, documented locations for operator-owned input and runtime state.

## Excluded

- all authored, acceptance, and test directive JSON files;
- active workspaces, directive dossiers, and generated review packets;
- runtime ledgers, checkpoints, provider responses, telemetry, and local state;
- credentials, `.env` files, cache files, and compiled Python artifacts;
- a prebuilt Docker image archive, because the prior archive would not represent this source revision.

## Operator-owned state

After launch, operators may create a directive under `directive_inputs/` and use `runtime_data/` or `operator_state/` locally. Those files are not public-package content and must not be committed.
