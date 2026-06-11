# Release Asset Notes

This update keeps the Docker image archive in the repository to preserve the guided handoff shape.

For future releases, consider moving large binary artifacts to GitHub Releases:

- `novali-v7-standalone.tar`
- packaged zip archives
- larger screenshot/video walkthroughs

Recommended future release layout:

- source and docs stay in git;
- large runnable artifacts attach to a tagged GitHub Release;
- root README links to the release asset and checksum;
- `image/image_archive_manifest.json` records tag, digest, size, and build timestamp.
