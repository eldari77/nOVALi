from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from operator_shell.handoff_package import (  # noqa: E402
    CANONICAL_IMAGE_ARCHIVE_NAME,
    CANONICAL_IMAGE_TAG,
    export_standalone_image_archive,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the standalone NOVALI Docker image to a zip-friendly archive for handoff packaging."
    )
    parser.add_argument(
        "--output",
        default=str(PACKAGE_ROOT / "dist" / "image" / CANONICAL_IMAGE_ARCHIVE_NAME),
        help="Target path for the docker save archive.",
    )
    parser.add_argument(
        "--image-tag",
        default=CANONICAL_IMAGE_TAG,
        help=f"Docker image tag to export. Defaults to {CANONICAL_IMAGE_TAG}.",
    )
    args = parser.parse_args()

    result = export_standalone_image_archive(
        output_path=args.output,
        image_tag=args.image_tag,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
