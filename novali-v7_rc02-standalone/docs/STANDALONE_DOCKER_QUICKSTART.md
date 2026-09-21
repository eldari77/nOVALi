# Docker Quick Start

From the repository root, run:

```powershell
.\launch\00_first_run_wizard.ps1
```

The wizard checks Docker, builds `novali-v7-standalone:local` from this package when it is absent, starts the local Web Operator, and opens `/shell`.

To build manually from the package root:

```powershell
docker build -t novali-v7-standalone:local .
docker run --rm -p 127.0.0.1:8787:8787 novali-v7-standalone:local
```

The operator-facing entrypoint is `python -m novali_v5.web_operator`. Direct bootstrap and main-module calls are developer or diagnostic paths, not the normal operator workflow.

The package has no bundled directive. Generate a local one with `standalone_docker/generate_directive_scaffold.ps1`, then load it through the Operator Shell. Keep the generated input, credentials, and all runtime output local.
