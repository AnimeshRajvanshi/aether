"""Sprint 9 Stage B — fetch IMD gridded Tmax years + ISD 2022 station files.

Both go ONLY to the gitignored cache (~/.aether_cache/sprint9_heat_stage_b/).
ISD raw station data is WMO-Resolution-40 restricted (non-US data "cannot be
redistributed") — it is never committed; the repo receives derived statistics
only, with provenance (interim probe-review ruling). IMD gridded gets the same
cache-raw/commit-derived handling until its license terms are verified
verbatim (Stage B report carries what the download page states).

IMD endpoint verified in Stage A: POST maxtemp.php, maxtemp=<year> ->
365/366 x 31 x 31 float32 little-endian, lat-major, 99.9 = missing,
grid 7.5..37.5 N x 67.5..97.5 E at 1.0 deg.
"""

from __future__ import annotations

import csv
import subprocess
import sys
import time
from pathlib import Path

import requests

CACHE = Path.home() / ".aether_cache" / "sprint9_heat_stage_b"
IMD_URL = "https://www.imdpune.gov.in/cmpg/Griddata/maxtemp.php"
ISD_URL = "https://www.ncei.noaa.gov/data/global-hourly/access/{year}/{station}.csv"
ISD_HISTORY = Path.home() / ".aether_cache" / "sprint9_heat_scan" / "isd-history.csv"

IMD_YEARS = [*range(1991, 2021), 2022]
ISD_YEAR = 2022

# Benchmark bbox
LAT_MIN, LAT_MAX = 22.375, 32.875
LON_MIN, LON_MAX = 67.875, 84.375


def fetch_imd() -> None:
    """curl subprocess, not requests: imdpune's TLS stack EOFs requests'
    sessions (observed) while plain curl works (Stage A probe). Retries with
    backoff; a year that still fails after 4 tries is recorded and skipped —
    the analysis step refuses to run with an incomplete baseline, so nothing
    fails silently."""
    out_dir = CACHE / "imd_maxtemp"
    out_dir.mkdir(parents=True, exist_ok=True)
    for year in IMD_YEARS:
        path = out_dir / f"maxtemp_{year}.grd"
        n_days = 366 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 365
        expected = n_days * 31 * 31 * 4
        if path.exists() and path.stat().st_size == expected:
            continue
        ok = False
        for attempt in range(4):
            proc = subprocess.run(
                [
                    "curl", "-s", "-m", "180", "--retry", "2",
                    "-X", "POST", IMD_URL,
                    "-d", f"maxtemp={year}",
                    "-o", str(path),
                ],
                check=False,
            )
            if proc.returncode == 0 and path.exists() and path.stat().st_size == expected:
                ok = True
                break
            time.sleep(3.0 * (attempt + 1))
        if ok:
            print(f"  imd {year}: {path.stat().st_size} bytes", flush=True)
        else:
            got = path.stat().st_size if path.exists() else 0
            path.unlink(missing_ok=True)
            (out_dir / "_failed.txt").open("a").write(f"{year} got={got} expected={expected}\n")
            print(f"  imd {year}: FAILED after retries (logged)", flush=True)
        time.sleep(1.5)  # be polite to IMD's server


def in_bbox_stations() -> list[dict[str, str]]:
    rows = [r for r in csv.DictReader(ISD_HISTORY.open()) if r["CTRY"] == "IN"]
    out = []
    for r in rows:
        try:
            lat, lon = float(r["LAT"]), float(r["LON"])
        except ValueError:
            continue
        if (
            LAT_MIN <= lat <= LAT_MAX
            and LON_MIN <= lon <= LON_MAX
            and r["BEGIN"] <= "20220402"
            and r["END"] >= "20220411"
        ):
            out.append(r)
    return out


def fetch_isd() -> None:
    out_dir = CACHE / "isd_2022"
    out_dir.mkdir(parents=True, exist_ok=True)
    stations = in_bbox_stations()
    print(f"  isd: {len(stations)} in-bbox stations", flush=True)
    ok = missing = 0
    for r in stations:
        sid = f"{r['USAF']}{r['WBAN']}"
        path = out_dir / f"{sid}.csv"
        if path.exists():
            ok += 1
            continue
        resp = requests.get(ISD_URL.format(year=ISD_YEAR, station=sid), timeout=120)
        if resp.status_code == 200 and resp.content:
            path.write_bytes(resp.content)
            ok += 1
        else:
            missing += 1
            (out_dir / "_missing.txt").open("a").write(f"{sid} HTTP {resp.status_code}\n")
    print(f"  isd: {ok} fetched/cached, {missing} missing (logged)", flush=True)


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "isd"):
        fetch_isd()
    if which in ("all", "imd"):
        fetch_imd()
    print("station/imd fetch complete", flush=True)


if __name__ == "__main__":
    main()
