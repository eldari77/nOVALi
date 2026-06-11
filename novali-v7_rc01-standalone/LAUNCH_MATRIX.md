# Launch Matrix

| Path | Purpose | Notes |
| --- | --- | --- |
| `launch/00_first_run_wizard.ps1` | Guided first run from repository root | Recommended for new operators |
| `standalone_docker/load_image_archive.ps1` | Load the packaged Docker image | Uses `image/novali-v7-standalone.tar` |
| `standalone_docker/run_web_operator_container.ps1` | Run the standalone Web Operator | Serves `/shell` on `127.0.0.1:8787` |
| `standalone_docker/generate_directive_scaffold.ps1` | Create a generic directive scaffold | Does not store secrets |

Use the Operator Shell for bootstrap, governed continuation, autonomy status, pause, and emergency stop.

