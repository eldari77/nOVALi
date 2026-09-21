# Release Assets

`novali-v7_rc02-standalone` intentionally does not include a Docker image archive: the available prior archive predates this source refresh.

The first-run wizard builds the image locally from the package Dockerfile. If a future release attaches an image or zip asset, publish it through a tagged GitHub Release with a version, checksum, build provenance, and a documented match to the packaged source revision.
