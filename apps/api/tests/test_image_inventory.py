"""GUARD image-inventory (Stage B gate addition): every file under /app/data
in the built image must be committed at the image's baked SHA — a positive
subset check against `git ls-tree`, not a pattern denylist.

Skipped unless AETHER_IMAGE_REF names a locally built image:

    AETHER_IMAGE_REF=aether-api:stage-b uv run pytest apps/api/tests/test_image_inventory.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

IMAGE = os.environ.get("AETHER_IMAGE_REF")

pytestmark = pytest.mark.skipif(
    not IMAGE, reason="AETHER_IMAGE_REF not set (image-inventory guard)"
)

_TOOL = Path(__file__).resolve().parents[3] / "tools" / "verify_image_inventory.py"


def test_image_data_files_all_committed_at_baked_sha() -> None:
    assert IMAGE is not None
    result = subprocess.run(
        [sys.executable, str(_TOOL), IMAGE], capture_output=True, text=True
    )
    assert result.returncode == 0, (
        f"image-inventory guard RED for {IMAGE}:\n{result.stdout}{result.stderr}"
    )
