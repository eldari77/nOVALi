# Public Package Contents

This file explains what the public guided handoff includes and excludes.

## Included

- runnable NOVALI v7 standalone package;
- Docker image archive or build path for local execution;
- React Operator Shell static build;
- generic directive scaffolding tools;
- generic trusted-source and Librarian seed documentation;
- public operator guides and quick references;
- sanitized screenshots;
- placeholder runtime folders with README files.

## Excluded

- private mission directive files from local runs;
- active workspace artifacts and generated dossiers from private runs;
- pending LLM directive candidates;
- runtime JSONL ledgers;
- local telemetry exports;
- spill-volume state;
- `.env` files;
- raw trusted-source provider output;
- API keys, tokens, passwords, and credential-shaped values.

## Why

The public handoff should be runnable and reviewable without becoming a dump of private runtime state. Operators should start from their own directive and let NOVALI create new local evidence under their own workspace.
