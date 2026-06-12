"""Image-inventory guard (Sprint 10 Stage B gate addition; required before any deploy).

POSITIVE SUBSET CHECK: every file under /app/data inside the built image must
be a committed path (``git ls-tree`` at the image's own baked SHA). The
.dockerignore denylist is belt; this guard is the suspenders — it goes red on
ANY in-image file that is not committed, regardless of why the denylist
missed it (gitignored working files, planted files, future pattern gaps).

Usage:
    uv run python tools/verify_image_inventory.py <image-ref>

Exit 0 = every image data file is committed at the baked SHA.
Exit 1 = violations (each printed) — the image is NOT the committed tree.

Requires docker and a git checkout containing the baked SHA. Wired as a
pytest guard via apps/api/tests/test_image_inventory.py (env-gated on
AETHER_IMAGE_REF) and intended for the CI deploy job before `flyctl deploy`.
"""

from __future__ import annotations

import json
import subprocess
import sys

DATA_PREFIX = "/app/data/"


def _run(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def image_baked_sha(image: str) -> str:
    """The AETHER_GIT_SHA env baked into the image (the build arg)."""
    raw = _run(["docker", "image", "inspect", "--format", "{{json .Config.Env}}", image])
    for entry in json.loads(raw):
        key, _, value = str(entry).partition("=")
        if key == "AETHER_GIT_SHA" and value:
            return value
    raise SystemExit(f"RED: image {image} carries no AETHER_GIT_SHA — cannot pin the check")


def image_data_files(image: str) -> list[str]:
    """Every regular file under /app/data inside the image."""
    out = _run(["docker", "run", "--rm", "--entrypoint", "find", image, "/app/data", "-type", "f"])
    return sorted(line for line in out.splitlines() if line.strip())


def committed_paths(sha: str) -> set[str]:
    """Every committed repo path at the given SHA."""
    return set(_run(["git", "ls-tree", "-r", "--name-only", sha]).splitlines())


def verify(image: str) -> int:
    sha = image_baked_sha(image)
    files = image_data_files(image)
    committed = committed_paths(sha)
    violations = [
        path
        for path in files
        if not path.startswith(DATA_PREFIX) or path[len(DATA_PREFIX) :] not in committed
    ]
    print(
        f"image {image} @ {sha[:12]}: {len(files)} files under /app/data, "
        f"{len(committed)} committed paths at the baked SHA"
    )
    if not files:
        print("RED: /app/data is empty — enumeration collapsed, refusing to pass")
        return 1
    if violations:
        print(f"RED: {len(violations)} in-image file(s) are NOT committed at {sha[:12]}:")
        for path in violations:
            print(f"  {path}")
        return 1
    print("GREEN: every in-image data file is committed at the baked SHA")
    return 0


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_image_inventory.py <image-ref>")
    raise SystemExit(verify(sys.argv[1]))


if __name__ == "__main__":
    main()
