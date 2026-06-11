# Standalone Docker Quickstart

## Recommended

Run the repository-level wizard:

```powershell
.\launch\00_first_run_wizard.ps1
```

## Manual

From this package directory:

```powershell
.\standalone_docker\load_image_archive.ps1
.\standalone_docker\run_web_operator_container.ps1
```

Then open:

```text
http://127.0.0.1:8787/shell
```

Trusted-source credentials are optional and must be supplied only through a private local environment or secret store.

