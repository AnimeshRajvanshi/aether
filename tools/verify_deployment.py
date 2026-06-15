"""Deployed-integrity verifier (Sprint 10 Stage D — the point of the sprint).

Given a live base URL, prove the deployed API serves byte-identical committed
artifacts AT THE SHA IT CLAIMS — never HEAD. The pin is the guard's validity:
every comparison is against the repo *at the SHA reported by /api/version*, so a
stale-but-internally-consistent deploy is distinguishable from real drift.

What it checks (no tolerance windows, no "close enough" hashing, no skipped
endpoints):

  (a) GET /api/version -> the deployed git SHA (40-hex; validated).
  (b) Read the repo at THAT SHA via `git show <sha>:<path>` (the manifest and
      every committed source) — never the working tree.
  (c) Raw-artifact endpoints: fetch each (per the manifest at the pinned SHA),
      hash the TRANSPORT-DECODED body, compare to the manifest SHA-256. Two
      independent transport paths — default (server may gzip/br; we decode) AND
      `Accept-Encoding: identity` (forces no compression). Either mismatch is
      RED, with the first differing byte offset + hex context reported.
  (d) Composed endpoints: reconstruct the expected payload by running the
      PINNED-SHA code over the PINNED-SHA data (the tree is extracted with
      `git archive <sha>` and imported via PYTHONPATH, asserted to load from the
      extract), then deep-equal against the live JSON.
  (e) Negative space: audit-excluded paths (NOAA ISD raw — non-redistributable
      under WMO Res. 40; the route-unreachable _nasa_k siblings; composed-source
      files; non-whitelisted events/layers) must return 404 from the live API.

Result classification (the SHA pin is what separates the middle case):
  GREEN   — pinned SHA == origin/main HEAD and every check passes.
  WARNING — every integrity check passes but the deploy is stale (pinned SHA is
            an ancestor of HEAD). Internally consistent; just not the latest
            main. Exit 0 — a stale deploy is not a drift.
  RED     — any byte mismatch / deep-equality failure / negative-space leak, OR
            the pinned SHA cannot be read locally (the pin is unverifiable).
            Exit 1.

Usage:
  python tools/verify_deployment.py https://aether-api-arkaneworks.fly.dev \
      [--json-out docs/reports/sprint10_stage_d_verification.json] [--strict]

`--strict` makes WARNING exit non-zero too (for a CI lane that demands the
deploy be exactly main HEAD).
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = "artifacts.manifest.json"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# Audit-excluded paths that MUST 404 (cardinal rule 3 made live-checkable). These
# are concrete instances; the route table structurally cannot serve them, and
# this asserts the live deployment agrees.
NEGATIVE_SPACE_URLS = [
    # NOAA ISD raw station data — non-redistributable (WMO Res. 40); provably
    # absent from the artifact set (Stage A). No route exists; must 404.
    "/api/events/india_nw_heatwave_2022_04/isd_raw.csv",
    "/api/events/india_nw_heatwave_2022_04/isd/stations.csv",
    "/api/isd/india_nw_heatwave_2022_04.csv",
    # _nasa_k sibling render set: shipped in the image but route-unreachable by
    # design (path params cannot contain '/'); must 404.
    "/api/events/turkmenistan_goturdepe_2022_08_15/_nasa_k/enhancement.png",
    "/api/events/turkmenistan_goturdepe_2022_08_15/_nasa_k/bounds.json",
    # composed-source files must never be raw-served (they reach clients only
    # through the composed endpoints, re-serialized).
    "/api/events/india_nw_heatwave_2022_04/validation.json",
    "/api/events/india_nw_heatwave_2022_04/uhi.json",
    "/api/events/turkmenistan_goturdepe_2022_08_15/q_estimate.json",
    # whitelist / non-existent (defense-in-depth, Stage A F2).
    "/api/events/not_a_real_event/enhancement.png",
    "/api/events/india_nw_heatwave_2022_04/layers/secret.png",
]

# Dump script: run by the pinned-SHA interpreter path to emit expected composed
# payloads. Asserts the imported package is the extracted tree, not the editable
# install — so the reconstruction is genuinely the pinned code.
_DUMP_SCRIPT = r"""
import json, sys
import aether_api
tree = sys.argv[1]
assert str(aether_api.__file__).startswith(tree), (
    f"aether_api loaded from {aether_api.__file__}, not the pinned extract {tree}"
)
from aether_api.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
out = {}
for url in sys.argv[2:]:
    r = client.get(url)
    out[url] = {"status": r.status_code, "json": r.json()}
sys.stdout.write(json.dumps(out))
"""


class Failure(dict[str, Any]):
    """A RED finding (kind + details), collected and reported."""


def _git_show_bytes(sha: str, path: str) -> bytes | None:
    proc = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "show", f"{sha}:{path}"],
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def _sha_known(sha: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "cat-file", "-e", f"{sha}^{{commit}}"],
            capture_output=True,
        ).returncode
        == 0
    )


def _head_sha() -> str:
    # origin/main if present, else HEAD — the "latest committed" reference.
    for ref in ("origin/main", "HEAD"):
        proc = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", ref], capture_output=True, text=True
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    return ""


def _is_ancestor(maybe_ancestor: str, descendant: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(REPO_ROOT), "merge-base", "--is-ancestor",
             maybe_ancestor, descendant],
            capture_output=True,
        ).returncode
        == 0
    )


def _first_diff(expected: bytes, got: bytes) -> dict[str, Any]:
    """First differing byte offset + a short hex context window for each side."""
    n = min(len(expected), len(got))
    off = next((i for i in range(n) if expected[i] != got[i]), n)
    lo = max(0, off - 8)

    def window(b: bytes) -> str:
        return binascii.hexlify(b[lo : off + 8]).decode()

    return {
        "first_diff_offset": off,
        "expected_len": len(expected),
        "got_len": len(got),
        "expected_hex_window": window(expected),
        "got_hex_window": window(got),
    }


def get_deployed_sha(client: httpx.Client) -> str:
    r = client.get("/api/version")
    r.raise_for_status()
    sha = str(r.json().get("git_sha", ""))
    if not SHA_RE.match(sha):
        raise SystemExit(
            f"RED: /api/version returned git_sha={sha!r}, not a 40-hex SHA — "
            "cannot pin the verification."
        )
    return sha


def verify_raw(client: httpx.Client, sha: str, manifest: dict[str, Any]) -> list[Failure]:
    failures: list[Failure] = []
    raw = manifest["raw_endpoints"]
    if len(raw) < 14:
        failures.append(Failure(kind="manifest_raw_underflow", count=len(raw)))
    for url, entry in sorted(raw.items()):
        committed = _git_show_bytes(sha, entry["source"])
        if committed is None:
            failures.append(Failure(kind="source_missing_at_sha", url=url, source=entry["source"]))
            continue
        committed_hash = hashlib.sha256(committed).hexdigest()
        if committed_hash != entry["sha256"]:
            # The manifest disagrees with the committed file AT the pinned SHA —
            # the manifest is internally stale at this SHA (staleness guard would
            # have caught it pre-merge). RED: the contract itself is unreliable.
            failures.append(
                Failure(
                    kind="manifest_internal_inconsistency",
                    url=url,
                    source=entry["source"],
                    manifest_sha256=entry["sha256"],
                    committed_sha256=committed_hash,
                )
            )
            continue
        for label, headers in (("default", {}), ("identity", {"Accept-Encoding": "identity"})):
            r = client.get(url, headers=headers)
            if r.status_code != 200:
                failures.append(
                    Failure(kind="raw_status", url=url, path=label, status=r.status_code)
                )
                continue
            body = r.content  # transport-decoded
            got = hashlib.sha256(body).hexdigest()
            if got != entry["sha256"]:
                failures.append(
                    Failure(
                        kind="raw_byte_mismatch",
                        url=url,
                        transport_path=label,
                        content_encoding=r.headers.get("content-encoding", "(none)"),
                        expected_sha256=entry["sha256"],
                        got_sha256=got,
                        **_first_diff(committed, body),
                    )
                )
    return failures


def verify_composed(client: httpx.Client, sha: str, manifest: dict[str, Any]) -> list[Failure]:
    failures: list[Failure] = []
    urls = sorted(manifest["composed_endpoints"].keys())
    with tempfile.TemporaryDirectory(prefix="verify_deploy_") as tmp:
        # Extract the pinned tree (code + data) and run its OWN loader.
        archive = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "archive", sha], capture_output=True
        )
        if archive.returncode != 0:
            return [Failure(kind="git_archive_failed", sha=sha)]
        subprocess.run(["tar", "-x", "-C", tmp], input=archive.stdout, check=True)
        pythonpath = ":".join(
            str(Path(tmp) / p)
            for p in ("apps/api", "eval/harness", "packages/causal", "packages/ontology")
        )
        env = {
            "PYTHONPATH": pythonpath,
            "AETHER_DATA_ROOT": tmp,
            "AETHER_ENV": "development",
            "PATH": __import__("os").environ.get("PATH", ""),
        }
        proc = subprocess.run(
            [sys.executable, "-c", _DUMP_SCRIPT, tmp, *urls],
            capture_output=True,
            text=True,
            env=env,
        )
        if proc.returncode != 0:
            return [Failure(kind="composed_reconstruction_failed", stderr=proc.stderr[-2000:])]
        expected = json.loads(proc.stdout)

    for url in urls:
        live = client.get(url)
        exp = expected[url]
        if live.status_code != exp["status"]:
            failures.append(
                Failure(
                    kind="composed_status", url=url, live=live.status_code,
                    expected=exp["status"],
                )
            )
            continue
        if live.json() != exp["json"]:
            failures.append(
                Failure(
                    kind="composed_deep_equality", url=url,
                    diff=_json_diff(exp["json"], live.json()),
                )
            )
    return failures


def _json_diff(expected: Any, got: Any, path: str = "$") -> dict[str, Any]:
    """First structural divergence path (so a RED points at the exact key)."""
    if type(expected) is not type(got):
        return {
            "path": path,
            "expected_type": type(expected).__name__,
            "got_type": type(got).__name__,
        }
    if isinstance(expected, dict):
        for k in expected.keys() | got.keys():
            if k not in expected or k not in got:
                return {
                    "path": f"{path}.{k}",
                    "missing_side": "got" if k in expected else "expected",
                }
            sub = _json_diff(expected[k], got[k], f"{path}.{k}")
            if sub:
                return sub
        return {}
    if isinstance(expected, list):
        if len(expected) != len(got):
            return {"path": path, "expected_len": len(expected), "got_len": len(got)}
        for i, (a, b) in enumerate(zip(expected, got, strict=True)):
            sub = _json_diff(a, b, f"{path}[{i}]")
            if sub:
                return sub
        return {}
    return {} if expected == got else {"path": path, "expected": expected, "got": got}


def verify_negative_space(client: httpx.Client) -> list[Failure]:
    failures: list[Failure] = []
    for url in NEGATIVE_SPACE_URLS:
        r = client.get(url)
        if r.status_code != 404:
            failures.append(Failure(kind="negative_space_leak", url=url, status=r.status_code))
    return failures


def classify(pinned_sha: str, head_sha: str, n_failures: int, stale: bool) -> tuple[str, str]:
    """Pure classification — the SHA pin is what separates WARNING from RED.

    RED on any failure (real drift / platform transformation / negative-space
    leak). Otherwise a deploy that passes every integrity check but is not main
    HEAD is a WARNING (stale or diverged), never RED: it is internally
    consistent, just not the latest commit.
    """
    if n_failures:
        return "RED", f"{n_failures} integrity failure(s) at pinned SHA {pinned_sha}."
    if head_sha and pinned_sha != head_sha:
        if stale:
            return "WARNING", (
                f"Deploy is internally consistent at {pinned_sha[:12]} but STALE: it is an "
                f"ancestor of main HEAD {head_sha[:12]}. Redeploy to advance; not a drift."
            )
        return "WARNING", (
            f"Deploy is internally consistent at {pinned_sha[:12]} but DIVERGED from main "
            f"HEAD {head_sha[:12]} (not an ancestor)."
        )
    return "GREEN", f"Deployed instance is provably the committed one at {pinned_sha[:12]}."


def run(base_url: str) -> dict[str, Any]:
    report: dict[str, Any] = {"base_url": base_url}
    with httpx.Client(base_url=base_url, timeout=30.0, follow_redirects=True) as client:
        sha = get_deployed_sha(client)
        report["pinned_sha"] = sha
        report["head_sha"] = _head_sha()
        if not _sha_known(sha):
            report["result"] = "RED"
            report["reason"] = (
                f"Deployed SHA {sha} is not present in the local repo — the pin is "
                "unverifiable. Fetch it (git fetch --all) and re-run."
            )
            report["failures"] = []
            return report

        manifest = json.loads(_git_show_bytes(sha, MANIFEST_PATH) or b"null")
        if not manifest:
            report["result"] = "RED"
            report["reason"] = f"No {MANIFEST_PATH} at pinned SHA {sha}."
            report["failures"] = []
            return report
        report["manifest_generated_at_commit"] = manifest.get("generated_at_commit")

        failures: list[Failure] = []
        failures += verify_raw(client, sha, manifest)
        failures += verify_composed(client, sha, manifest)
        failures += verify_negative_space(client)
        report["failures"] = failures
        report["counts"] = {
            "raw_endpoints": len(manifest["raw_endpoints"]),
            "composed_endpoints": len(manifest["composed_endpoints"]),
            "negative_space_checks": len(NEGATIVE_SPACE_URLS),
        }

        head = report["head_sha"]
        stale = bool(head) and sha != head and _is_ancestor(sha, head)
        report["result"], report["reason"] = classify(sha, head, len(failures), stale)
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Deployed-integrity verifier (Stage D).")
    ap.add_argument("base_url", help="Live API base URL, e.g. https://aether-api-arkaneworks.fly.dev")
    ap.add_argument("--json-out", type=Path, help="Write the full JSON report here.")
    ap.add_argument("--strict", action="store_true", help="Treat WARNING (stale) as failure too.")
    args = ap.parse_args()

    report = run(args.base_url)
    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2) + "\n")

    result = report["result"]
    print("\n=== DEPLOYED-INTEGRITY VERIFIER ===")
    print(f"base_url   : {report['base_url']}")
    print(f"pinned SHA : {report.get('pinned_sha', '(none)')}")
    print(f"main HEAD  : {report.get('head_sha', '(unknown)')}")
    if "counts" in report:
        c = report["counts"]
        print(
            f"checked    : {c['raw_endpoints']} raw (x2 transport paths) + "
            f"{c['composed_endpoints']} composed + {c['negative_space_checks']} negative-space"
        )
    print(f"RESULT     : {result}")
    print(f"reason     : {report['reason']}")
    for f in report.get("failures", []):
        print(f"  FAIL {f.get('kind')}: {json.dumps({k: v for k, v in f.items() if k != 'kind'})}")

    if result == "RED" or (result == "WARNING" and args.strict):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
