# Launch Helpers

Use `02_run_browser_operator.bat` or `02_run_browser_operator.ps1` as the primary packaged run helpers.

Those helpers preserve the existing canonical authority flow; they do not create a second authority path.

When Docker Desktop is healthy they launch the packaged container path. If Docker is unavailable or unhealthy and local Python is present, they fall back to the packaged local Python operator against the same package-root state directories.
