"""Unit tests for the deployed-integrity verifier (Stage D).

These prove the guard's decision logic WITHOUT a live broken deploy:
- classify(): GREEN / WARNING (stale, diverged) / RED.
- _first_diff(): the first-differing-byte report a RED carries.
- _json_diff(): the structural path a composed deep-equality RED carries.
- verify_raw(): a tampered body IS caught (raw_byte_mismatch with offset), via a
  MockTransport serving the committed bytes at HEAD (truth) vs a flipped byte.
- verify_negative_space(): a leaked (200) audit-excluded path IS caught.

The composed reconstruction (git-archive + pinned-code subprocess) and the
end-to-end pass are exercised by the live run committed as gate evidence.
"""

from __future__ import annotations

import subprocess

import httpx
import pytest
import verify_deployment as vd


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


# --------------------------------------------------------------------------- #
# classify — the SHA pin separates WARNING from RED
# --------------------------------------------------------------------------- #
def test_classify_green_when_head_and_clean() -> None:
    result, reason = vd.classify("a" * 40, "a" * 40, 0, stale=False)
    assert result == "GREEN"
    assert "provably the committed one" in reason


def test_classify_warning_when_stale_but_clean() -> None:
    result, reason = vd.classify("a" * 40, "b" * 40, 0, stale=True)
    assert result == "WARNING"
    assert "STALE" in reason and "not a drift" in reason


def test_classify_warning_when_diverged_but_clean() -> None:
    result, reason = vd.classify("a" * 40, "b" * 40, 0, stale=False)
    assert result == "WARNING"
    assert "DIVERGED" in reason


def test_classify_red_on_any_failure_even_at_head() -> None:
    # A failure outranks staleness: drift at HEAD is RED, not GREEN.
    result, _ = vd.classify("a" * 40, "a" * 40, 1, stale=False)
    assert result == "RED"
    result2, _ = vd.classify("a" * 40, "b" * 40, 3, stale=True)
    assert result2 == "RED"


# --------------------------------------------------------------------------- #
# _first_diff / _json_diff — the detail a RED reports
# --------------------------------------------------------------------------- #
def test_first_diff_identical() -> None:
    d = vd._first_diff(b"abcdef", b"abcdef")
    assert d["first_diff_offset"] == 6  # == len -> no difference within overlap


def test_first_diff_reports_offset_and_windows() -> None:
    d = vd._first_diff(b"abcdef", b"abXdef")
    assert d["first_diff_offset"] == 2
    assert d["expected_hex_window"] != d["got_hex_window"]


def test_first_diff_length_mismatch() -> None:
    d = vd._first_diff(b"abc", b"abcde")
    assert d["expected_len"] == 3 and d["got_len"] == 5


def test_json_diff_equal() -> None:
    assert vd._json_diff({"a": [1, 2]}, {"a": [1, 2]}) == {}


def test_json_diff_value_path() -> None:
    diff = vd._json_diff({"a": {"b": 1}}, {"a": {"b": 2}})
    assert diff["path"] == "$.a.b" and diff["expected"] == 1 and diff["got"] == 2


def test_json_diff_missing_key_and_list_len() -> None:
    assert vd._json_diff({"a": 1}, {})["missing_side"] == "got"
    assert vd._json_diff([1, 2], [1])["expected_len"] == 2


# --------------------------------------------------------------------------- #
# verify_raw — a tampered body is caught (mock serving committed bytes at HEAD)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def head_manifest() -> tuple[str, dict]:
    import json

    sha = _head()
    manifest = json.loads(vd._git_show_bytes(sha, vd.MANIFEST_PATH) or b"null")
    assert manifest, "no manifest at HEAD"
    return sha, manifest


def _client(serve: dict[str, bytes], leak_200: set[str] = frozenset()) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path in serve:
            return httpx.Response(200, content=serve[path])
        if path in leak_200:
            return httpx.Response(200, content=b"LEAK")
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def test_verify_raw_passes_on_committed_bytes(head_manifest: tuple[str, dict]) -> None:
    sha, manifest = head_manifest
    serve = {
        url: vd._git_show_bytes(sha, entry["source"]) or b""
        for url, entry in manifest["raw_endpoints"].items()
    }
    with _client(serve) as client:
        assert vd.verify_raw(client, sha, manifest) == []


def test_verify_raw_detects_a_single_flipped_byte(head_manifest: tuple[str, dict]) -> None:
    sha, manifest = head_manifest
    serve = {
        url: vd._git_show_bytes(sha, entry["source"]) or b""
        for url, entry in manifest["raw_endpoints"].items()
    }
    target = sorted(serve)[0]
    original = bytearray(serve[target])
    original[len(original) // 2] ^= 0xFF  # flip one byte mid-file
    serve[target] = bytes(original)
    with _client(serve) as client:
        failures = vd.verify_raw(client, sha, manifest)
    mismatches = [f for f in failures if f["kind"] == "raw_byte_mismatch" and f["url"] == target]
    assert mismatches, "a flipped byte must be caught as raw_byte_mismatch"
    assert mismatches[0]["first_diff_offset"] == len(original) // 2


# --------------------------------------------------------------------------- #
# verify_negative_space — a leaked audit-excluded path is caught
# --------------------------------------------------------------------------- #
def test_negative_space_all_404_passes() -> None:
    with _client({}) as client:
        assert vd.verify_negative_space(client) == []


def test_negative_space_leak_is_caught() -> None:
    leaked = vd.NEGATIVE_SPACE_URLS[0]
    with _client({}, leak_200={leaked}) as client:
        failures = vd.verify_negative_space(client)
    assert [f["url"] for f in failures] == [leaked]
    assert failures[0]["kind"] == "negative_space_leak"
