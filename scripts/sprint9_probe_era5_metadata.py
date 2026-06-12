"""Sprint 9 Stage A — ERA5 ARCO metadata probe (heat vertical).

Verifies, without assuming, that the ARCO-ERA5 stores carry the variables the
heat vertical needs (2 m temperature, soil moisture, geopotential, winds,
humidity), what time range each store covers, and what the chunk layout is —
the chunking decides whether a multi-decade climatology scan is affordable, so
it must be measured, not guessed.

Probe only: reads Zarr metadata + a single sample chunk; no bulk download.
Output: stage_a_outputs/sprint9_heat_probe/era5_metadata.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import xarray as xr

OUT_DIR = Path(__file__).resolve().parents[1] / "stage_a_outputs" / "sprint9_heat_probe"

# The operational store (already used by packages/data_spine/era5.py) and the
# 1-degree coarsened store (candidate for the cheap climatology scan).
STORES = {
    "full_37-1h-0p25deg-chunk-1.zarr-v3": (
        "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3"
    ),
    "1959-2022-1h-360x181_equiangular_with_poles_conservative.zarr": (
        "gs://gcp-public-data-arco-era5/ar/"
        "1959-2022-1h-360x181_equiangular_with_poles_conservative.zarr"
    ),
}

# Variables the heat vertical needs (task brief, Stage A item 1).
WANTED = [
    "2m_temperature",
    "2m_dewpoint_temperature",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "surface_pressure",
    "geopotential",  # pressure-level (synoptic ridge diagnostics)
    "volumetric_soil_water_layer_1",
    "volumetric_soil_water_layer_2",
    "volumetric_soil_water_layer_3",
    "volumetric_soil_water_layer_4",
    "mean_sea_level_pressure",
    "total_precipitation",
]


def probe_store(uri: str) -> dict[str, Any]:
    """Open a store lazily and report coverage + per-variable chunk economics."""
    ds = xr.open_zarr(uri, consolidated=True, storage_options={"token": "anon"})
    time = ds["time"]
    info: dict[str, Any] = {
        "uri": uri,
        "time_start": str(time.values[0]),
        "time_end": str(time.values[-1]),
        "n_time": int(time.size),
        "grid": {
            "n_lat": int(ds.sizes.get("latitude", 0)),
            "n_lon": int(ds.sizes.get("longitude", 0)),
        },
        "variables": {},
        "missing": [],
    }
    for name in WANTED:
        if name not in ds:
            info["missing"].append(name)
            continue
        var = ds[name]
        enc_chunks = var.encoding.get("chunks") or getattr(var.data, "chunksize", None)
        info["variables"][name] = {
            "dims": list(var.dims),
            "shape": [int(s) for s in var.shape],
            "chunks": [int(c) for c in enc_chunks] if enc_chunks else None,
            "dtype": str(var.dtype),
        }
    ds.close()
    return info


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {key: probe_store(uri) for key, uri in STORES.items()}
    out = OUT_DIR / "era5_metadata.json"
    out.write_text(json.dumps(results, indent=2))
    for key, r in results.items():
        print(f"== {key}")
        print(f"   time: {r['time_start']} .. {r['time_end']}  (n={r['n_time']})")
        print(f"   grid: {r['grid']}")
        print(f"   missing: {r['missing']}")
        for v, m in r["variables"].items():
            print(f"   {v}: dims={m['dims']} chunks={m['chunks']}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
