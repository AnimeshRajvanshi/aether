"""Sprint 9 Stage B — fetch MODIS LST COGs from Microsoft Planetary Computer.

Route decision (documented in the Stage B report): MOD11 v061 at LP DAAC is
HDF4-EOS2, which this environment's rasterio/GDAL wheel cannot read (no HDF4
driver — probed, not assumed). MPC mirrors the SAME NASA v061 product as
per-subdataset COGs (collections modis-11A1-061 / modis-11A2-061), anonymously
readable with a short-lived SAS token. LP DAAC remains the archival source;
the Stage A Earthdata-auth probe stands.

Fetched into the gitignored cache:
- MOD11A1 daily, 2022-04-01..12, tiles over the event bbox:
  LST_Day_1km + QC_Day + Day_view_time.
- MOD11A2 8-day composites containing the window (day-of-year 089, 097),
  2013-2021 (the LST climatology baseline) + 2022 (the composite-vs-daily
  residual check): LST_Day_1km + QC_Day + Day_view_time.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

CACHE = Path.home() / ".aether_cache" / "sprint9_heat_stage_b" / "modis"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
SAS = "https://planetarycomputer.microsoft.com/api/sas/v1/token/{collection}"
BBOX = [67.875, 22.375, 84.375, 32.875]

A1_ASSETS = ["LST_Day_1km", "QC_Day", "Day_view_time"]
A2_ASSETS = ["LST_Day_1km", "QC_Day", "Day_view_time"]


def stac_items(collection: str, datetime_range: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    body: dict[str, Any] = {
        "collections": [collection],
        "bbox": BBOX,
        "datetime": datetime_range,
        "limit": 250,
    }
    next_body: dict[str, Any] | None = body
    while next_body is not None:
        r = requests.post(STAC, json=next_body, timeout=120)
        r.raise_for_status()
        page = r.json()
        items.extend(page.get("features", []))
        next_body = None
        for link in page.get("links", []):
            if link.get("rel") == "next" and link.get("body"):
                next_body = link["body"]
    return items


def get_token_for_href(href: str) -> str:
    """SAS token for the asset's actual storage account/container.

    The collection-keyed token endpoint returned a token that the blobs 403'd
    (observed); the account/container form authorizes correctly.
    """
    host = href.split("/")[2]  # <account>.blob.core.windows.net
    account = host.split(".")[0]
    container = href.split("/")[3]
    r = requests.get(SAS.format(collection=f"{account}/{container}"), timeout=60)
    r.raise_for_status()
    return str(r.json()["token"])


def fetch(collection: str, datetime_range: str, assets: list[str]) -> None:
    items = stac_items(collection, datetime_range)
    print(f"{collection} {datetime_range}: {len(items)} items", flush=True)
    # Token PER storage account/container of the asset being fetched — an
    # item's assets can span containers (the 'hdf' mirror lives elsewhere),
    # so a token derived from "any asset" 403s on the others (observed).
    tokens: dict[str, tuple[str, float]] = {}
    out_dir = CACHE / collection
    out_dir.mkdir(parents=True, exist_ok=True)
    n_ok = 0
    for item in items:
        for asset_key in assets:
            asset = item["assets"].get(asset_key)
            if asset is None:
                (out_dir / "_missing_assets.txt").open("a").write(
                    f"{item['id']} {asset_key}\n"
                )
                continue
            path = out_dir / f"{item['id']}_{asset_key}.tif"
            if path.exists() and path.stat().st_size > 0:
                n_ok += 1
                continue
            href = asset["href"]
            key = "/".join(href.split("/")[2:4])  # account-host/container
            token, t0 = tokens.get(key, ("", 0.0))
            if not token or time.time() - t0 > 1800:
                token = get_token_for_href(href)
                tokens[key] = (token, time.time())
            url = href + "?" + token
            for attempt in range(3):
                try:
                    r = requests.get(url, timeout=300)
                    r.raise_for_status()
                    path.write_bytes(r.content)
                    n_ok += 1
                    break
                except requests.RequestException as exc:
                    if attempt == 2:
                        (out_dir / "_failed.txt").open("a").write(
                            f"{item['id']} {asset_key}: {exc}\n"
                        )
                    time.sleep(2.0 * (attempt + 1))
    # item inventory for provenance
    inv = [
        {"id": it["id"], "datetime": it["properties"].get("datetime") or
         it["properties"].get("start_datetime")}
        for it in items
    ]
    (out_dir / f"_inventory_{datetime_range[:10]}.json").write_text(json.dumps(inv, indent=1))
    print(f"{collection}: {n_ok} assets cached", flush=True)


def main() -> None:
    # Daily granules across the canonical window (+1 day each side for the
    # view-time record): Apr 1..12.
    fetch("modis-11A1-061", "2022-04-01T00:00:00Z/2022-04-12T23:59:59Z", A1_ASSETS)
    # 8-day composites 089 (Mar 30) + 097 (Apr 7) for baseline years + 2022.
    for year in [*range(2013, 2022), 2022]:
        fetch(
            "modis-11A2-061",
            f"{year}-03-29T00:00:00Z/{year}-04-08T23:59:59Z",
            A2_ASSETS,
        )
    print("modis fetch complete", flush=True)


if __name__ == "__main__":
    main()
