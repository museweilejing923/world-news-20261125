#!/usr/bin/env python3
"""Copy the pre-rendered 25 November 2026 world-news image to the output.

Standard library only, so it runs in a bare Python sandbox with no
network and no third-party packages: the image itself is entry.png,
kept next to this file in the repository.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "entry.png")


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, "entry.png")
    shutil.copyfile(SRC, dst)
    if not os.path.isfile(dst) or os.path.getsize(dst) == 0:
        raise SystemExit("entry.png was not written correctly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
