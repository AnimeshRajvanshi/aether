"""Sprint 10 Stage B deployment guard suite.

Each guard is named for what it FAILS on (the Stage B gate reads this file as
the guard inventory):

- GUARD read-only:        fails if any route accepts a mutating HTTP method.
- GUARD CORS-foreign:     fails if a production-configured app honors a
                          foreign origin (header echo or preflight pass).
- GUARD CORS-wildcard:    fails if wildcard origins are accepted in config.
- GUARD config-loud:      fails if production starts without required env
                          (allowed origins, git SHA) instead of crashing.
- GUARD version-baked:    fails if /api/version invents a SHA instead of
                          reporting the baked build arg (or honest 'dev').
- GUARD byte-identity:    fails if any single-file endpoint serves bytes that
                          differ from the committed file.
- GUARD event-whitelist:  fails if asset routes serve a path that exists on
                          disk but is not a registered event (Stage A F2).
- GUARD security-headers: fails if responses (200 and 404) drop the header set.
- GUARD startup-schema:   fails if the app starts while a committed
                          attribution artifact violates its schema.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from aether_api import __version__, config, loaders
from aether_api.main import app, create_app
from fastapi.testclient import TestClient

GOTURDEPE = "turkmenistan_goturdepe_2022_08_15"
PERMIAN = "permian_basin_2022"
INDIA = "india_nw_heatwave_2022_04"

PROD_ORIGIN = "https://aether.arkaneworks.co"
FOREIGN_ORIGIN = "https://evil.example.com"

client = TestClient(app)


def _set_prod_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHER_ENV", "production")
    monkeypatch.setenv("AETHER_ALLOWED_ORIGINS", PROD_ORIGIN)
    monkeypatch.setenv("AETHER_GIT_SHA", "abc1234deadbeef")


# --------------------------------------------------------------------------- #
# GUARD read-only
# --------------------------------------------------------------------------- #
def test_route_table_is_read_only() -> None:
    """Walk the LIVE route table; fail on any mutating method anywhere."""
    allowed = {"GET", "HEAD", "OPTIONS"}
    for route in app.routes:
        methods = set(getattr(route, "methods", None) or [])
        assert methods <= allowed, (
            f"Route {route.path!r} declares mutating methods {methods - allowed} — "
            "the API is a read-only artifact server."
        )


# --------------------------------------------------------------------------- #
# GUARD CORS-foreign / CORS-wildcard / config-loud
# --------------------------------------------------------------------------- #
def test_production_cors_rejects_foreign_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_prod_env(monkeypatch)
    prod_client = TestClient(create_app())

    # Simple request from a foreign origin: no CORS grant may be echoed.
    res = prod_client.get("/api/health", headers={"Origin": FOREIGN_ORIGIN})
    assert "access-control-allow-origin" not in res.headers

    # Preflight from a foreign origin must be refused outright.
    pre = prod_client.options(
        "/api/health",
        headers={"Origin": FOREIGN_ORIGIN, "Access-Control-Request-Method": "GET"},
    )
    assert pre.status_code == 400

    # The real production origin IS granted (the policy is tight, not broken).
    ok = prod_client.get("/api/health", headers={"Origin": PROD_ORIGIN})
    assert ok.headers.get("access-control-allow-origin") == PROD_ORIGIN


def test_wildcard_origins_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_prod_env(monkeypatch)
    monkeypatch.setenv("AETHER_ALLOWED_ORIGINS", "*")
    with pytest.raises(config.ConfigError, match=r"[Ww]ildcard"):
        create_app()
    monkeypatch.setenv("AETHER_ALLOWED_ORIGINS", f"{PROD_ORIGIN},https://*.example.com")
    with pytest.raises(config.ConfigError, match=r"[Ww]ildcard"):
        create_app()


def test_production_without_allowed_origins_fails_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_prod_env(monkeypatch)
    monkeypatch.delenv("AETHER_ALLOWED_ORIGINS")
    with pytest.raises(config.ConfigError, match="AETHER_ALLOWED_ORIGINS"):
        create_app()


def test_production_without_git_sha_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_prod_env(monkeypatch)
    monkeypatch.delenv("AETHER_GIT_SHA")
    with pytest.raises(config.ConfigError, match="AETHER_GIT_SHA"):
        create_app()


def test_malformed_origin_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_prod_env(monkeypatch)
    monkeypatch.setenv("AETHER_ALLOWED_ORIGINS", "aether.arkaneworks.co")  # no scheme
    with pytest.raises(config.ConfigError, match="scheme"):
        create_app()


# --------------------------------------------------------------------------- #
# GUARD version-baked
# --------------------------------------------------------------------------- #
def test_version_reports_baked_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_prod_env(monkeypatch)
    res = TestClient(create_app()).get("/api/version")
    assert res.status_code == 200
    assert res.json() == {"git_sha": "abc1234deadbeef", "app_version": __version__}


def test_version_is_honest_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AETHER_ENV", raising=False)
    monkeypatch.delenv("AETHER_GIT_SHA", raising=False)
    res = TestClient(create_app()).get("/api/version")
    assert res.json()["git_sha"] == "dev"  # honest, never an invented SHA


# --------------------------------------------------------------------------- #
# GUARD byte-identity
# --------------------------------------------------------------------------- #
def _raw_endpoint_map() -> list[tuple[str, Path]]:
    """Every single-file endpoint and the committed file it must equal."""
    pairs: list[tuple[str, Path]] = []
    for event_id in loaders.EVENT_IDS:
        adir = config.assets_dir(event_id)
        for url, path in [
            (f"/api/events/{event_id}/enhancement.png", adir / "enhancement.png"),
            (f"/api/events/{event_id}/nasa.png", adir / "nasa.png"),
            (f"/api/events/{event_id}/diff.png", adir / "diff.png"),
            (f"/api/events/{event_id}/bounds", adir / "bounds.json"),
            (f"/api/events/{event_id}/mask.geojson", adir / "mask.geojson"),
        ]:
            if path.exists():
                pairs.append((url, path))
        bounds_path = adir / "bounds.json"
        if bounds_path.exists():
            for layer in json.loads(bounds_path.read_text()).get("layers", []):
                layer_file = adir / f"{layer}.png"
                if layer_file.exists():
                    pairs.append((f"/api/events/{event_id}/layers/{layer}.png", layer_file))
        hp = loaders.hypotheses_path(event_id)
        if hp is not None:
            pairs.append((f"/api/events/{event_id}/hypotheses", hp))
        fp = loaders.factor_hypotheses_path(event_id)
        if fp is not None:
            pairs.append((f"/api/events/{event_id}/factor-hypotheses", fp))
    return pairs


def test_single_file_endpoints_serve_committed_bytes() -> None:
    pairs = _raw_endpoint_map()
    # Sanity floor: all three events must contribute raw endpoints.
    assert len(pairs) >= 14, f"raw endpoint enumeration collapsed: {len(pairs)}"
    for url, path in pairs:
        res = client.get(url)
        assert res.status_code == 200, url
        assert res.content == path.read_bytes(), (
            f"{url} does not serve the committed bytes of {path} — "
            "byte-identity through the stack is broken."
        )


def test_attribution_artifacts_pass_schema_validation() -> None:
    """The validation the raw-streaming split moved out of the request path:
    every streamable artifact must round-trip its extra='forbid' schema."""
    assert loaders.get_hypotheses(GOTURDEPE) is not None
    assert loaders.get_hypotheses(PERMIAN) is not None
    assert loaders.get_factor_hypotheses(INDIA) is not None


# --------------------------------------------------------------------------- #
# GUARD event-whitelist (Stage A finding F2)
# --------------------------------------------------------------------------- #
def test_unregistered_event_404s_even_when_files_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    planted = tmp_path / "evil_event"
    planted.mkdir()
    real = config.assets_dir(GOTURDEPE)
    shutil.copyfile(real / "enhancement.png", planted / "enhancement.png")
    shutil.copyfile(real / "bounds.json", planted / "bounds.json")
    monkeypatch.setattr(config, "ASSETS_ROOT", tmp_path)
    for url in (
        "/api/events/evil_event/enhancement.png",
        "/api/events/evil_event/bounds",
        "/api/events/evil_event/layers/enhancement.png",
        "/api/events/evil_event/hypotheses",
        "/api/events/evil_event/factor-hypotheses",
    ):
        assert client.get(url).status_code == 404, (
            f"{url} served a planted, unregistered event — the whitelist guard failed"
        )


# --------------------------------------------------------------------------- #
# GUARD security-headers
# --------------------------------------------------------------------------- #
def test_security_headers_on_success_and_error() -> None:
    for url, expected_status in [("/api/health", 200), ("/api/events/nope", 404)]:
        res = client.get(url)
        assert res.status_code == expected_status
        assert res.headers.get("x-content-type-options") == "nosniff"
        assert res.headers.get("x-frame-options") == "DENY"
        assert res.headers.get("referrer-policy") == "no-referrer"


# --------------------------------------------------------------------------- #
# GUARD startup-schema
# --------------------------------------------------------------------------- #
def test_startup_refuses_invalid_committed_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Negative test: corrupt a (copied) attribution artifact and assert the
    app refuses to START — the raw-streaming split must never silently serve
    an artifact that no longer passes its own schema."""
    stage_b = tmp_path / "stage_b_outputs" / GOTURDEPE
    stage_b.mkdir(parents=True)
    shutil.copyfile(
        config.stage_b_dir(GOTURDEPE) / "q_estimate.json", stage_b / "q_estimate.json"
    )
    attrib = tmp_path / "attribution_outputs" / GOTURDEPE
    attrib.mkdir(parents=True)
    (attrib / "hypotheses.json").write_text('{"bogus": "not a HypothesisSet"}')
    monkeypatch.setenv("AETHER_DATA_ROOT", str(tmp_path))
    with pytest.raises(config.ConfigError, match="failed schema validation"):
        create_app()
