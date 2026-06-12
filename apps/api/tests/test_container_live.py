"""GUARD container-parity: the suite's endpoint checks replayed against a LIVE
server (the local `docker run` of the Stage B image, later any deployed base
URL on a trusted network path).

Skipped unless AETHER_LIVE_BASE_URL is set — e.g.:

    AETHER_LIVE_BASE_URL=http://localhost:8080 \
    AETHER_LIVE_EXPECT_SHA=$(git rev-parse HEAD) \
    uv run pytest apps/api/tests/test_container_live.py -q

What it proves: the containerized API serves (a) byte-identical raw artifacts
per artifacts.manifest.json, (b) composed payloads deep-equal to the in-process
app over the same committed tree, (c) the baked SHA, (d) read-only + security
headers + whitelist behavior. This is the local precursor of the Stage D
deployed-integrity verifier (which adds SHA-pinned checkout + transport-
decoding semantics for platform proxies).
"""

from __future__ import annotations

import hashlib
import json
import os

import httpx
import pytest
from aether_api import manifest
from aether_api.main import app
from fastapi.testclient import TestClient

BASE_URL = os.environ.get("AETHER_LIVE_BASE_URL")

pytestmark = pytest.mark.skipif(
    not BASE_URL, reason="AETHER_LIVE_BASE_URL not set (live-container guard)"
)


@pytest.fixture(scope="module")
def live() -> httpx.Client:
    assert BASE_URL is not None
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        yield client


local = TestClient(app)


def test_live_health(live: httpx.Client) -> None:
    res = live.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_live_version_reports_expected_sha(live: httpx.Client) -> None:
    body = live.get("/api/version").json()
    assert body["git_sha"] not in ("", "dev"), "live server must carry a baked SHA"
    expected = os.environ.get("AETHER_LIVE_EXPECT_SHA")
    if expected:
        assert body["git_sha"] == expected, (
            f"live SHA {body['git_sha']} != expected {expected} — stale image?"
        )


def test_live_raw_endpoints_byte_identical_to_manifest(live: httpx.Client) -> None:
    committed = json.loads(manifest.manifest_path().read_text())
    raw = committed["raw_endpoints"]
    assert len(raw) >= 14
    for url, entry in raw.items():
        res = live.get(url)
        assert res.status_code == 200, url
        digest = hashlib.sha256(res.content).hexdigest()
        assert digest == entry["sha256"], (
            f"{url}: live bytes (sha256 {digest[:12]}…) != committed "
            f"({entry['sha256'][:12]}…) — byte-identity broken in the container"
        )


def test_live_composed_endpoints_deep_equal_local(live: httpx.Client) -> None:
    for url in ["/api/events"] + [
        f"/api/events/{e}"
        for e in (
            "turkmenistan_goturdepe_2022_08_15",
            "permian_basin_2022",
            "india_nw_heatwave_2022_04",
        )
    ]:
        assert live.get(url).json() == local.get(url).json(), url


def test_live_is_read_only_and_hardened(live: httpx.Client) -> None:
    assert live.post("/api/events").status_code == 405
    assert live.delete("/api/events/turkmenistan_goturdepe_2022_08_15").status_code == 405
    res = live.get("/api/health")
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert live.get("/api/events/evil_event/enhancement.png").status_code == 404
