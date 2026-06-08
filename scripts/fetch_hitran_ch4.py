"""Fetch the HITRAN methane line list over the Sprint 2 EMIT methane window.

Deterministic, one-time fetch of the CH4 line subset from HITRAN (via HAPI) that
our independent unit-absorption spectrum ``k`` is built from. The fetched line
data is committed so ``k`` generation is reproducible offline without re-hitting
HITRAN.

Window: the EXACT Sprint 2 matched-filter window
``aether_detection.constants.MF_SPECTRAL_WINDOWS_NM`` (2137-2493 nm), converted
to wavenumber (4011.2-4679.5 cm^-1) and padded by a margin so Voigt line wings
near the band edges are included.

Spectroscopy source (verified):
  HITRAN2020 — Gordon, I.E. et al. (2022). JQSRT 277, 107949.
               doi:10.1016/j.jqsrt.2021.107949
  HAPI       — Kochanov, R.V. et al. (2016). JQSRT 177, 15-30.
               doi:10.1016/j.jqsrt.2016.03.005

NASA's per-granule target file is NOT read here or anywhere in k generation.

Run from the repo root:  uv run python scripts/fetch_hitran_ch4.py
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")  # HAPI emits regex SyntaxWarnings on import

import hapi  # noqa: E402
from aether_detection.constants import MF_SPECTRAL_WINDOWS_NM  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "packages" / "detection" / "aether_detection" / "resources" / "hitran"
TABLE = "CH4_win"

# HITRAN global isotopologue IDs for methane (molecule 6):
#   32 = 12CH4, 33 = 13CH4, 34 = 12CH3D, 35 = 13CH3D  (the four main isotopologues)
CH4_ISO_GLOBAL_IDS = [32, 33, 34, 35]
WAVENUMBER_MARGIN_CM = 60.0  # pad each side for line wings near the window edges


def _window_wavenumbers() -> tuple[float, float]:
    """Sprint 2 window (nm) -> wavenumber range (cm^-1), padded by the margin."""
    lo_nm = min(w[0] for w in MF_SPECTRAL_WINDOWS_NM)
    hi_nm = max(w[1] for w in MF_SPECTRAL_WINDOWS_NM)
    numin = 1.0e7 / hi_nm - WAVENUMBER_MARGIN_CM
    numax = 1.0e7 / lo_nm + WAVENUMBER_MARGIN_CM
    return numin, numax


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    numin, numax = _window_wavenumbers()
    hapi.db_begin(str(OUT_DIR))
    print(f"Fetching CH4 (iso {CH4_ISO_GLOBAL_IDS}) over {numin:.2f}-{numax:.2f} cm^-1 ...")
    hapi.fetch_by_ids(TABLE, CH4_ISO_GLOBAL_IDS, numin, numax)
    n_rows = int(hapi.LOCAL_TABLE_CACHE[TABLE]["header"]["number_of_rows"])

    provenance = {
        "table": TABLE,
        "database": "HITRAN2020 (line-by-line) via HAPI",
        "hitran2020_doi": "10.1016/j.jqsrt.2021.107949",
        "hapi_doi": "10.1016/j.jqsrt.2016.03.005",
        "molecule": "CH4 (HITRAN molecule 6)",
        "isotopologue_global_ids": CH4_ISO_GLOBAL_IDS,
        "wavenumber_min_cm": numin,
        "wavenumber_max_cm": numax,
        "wavelength_window_nm": [
            min(w[0] for w in MF_SPECTRAL_WINDOWS_NM),
            max(w[1] for w in MF_SPECTRAL_WINDOWS_NM),
        ],
        "wavenumber_margin_cm": WAVENUMBER_MARGIN_CM,
        "n_lines": n_rows,
        "note": "Fetched verbatim from HITRAN; NASA's per-granule target file is NOT used.",
    }
    (OUT_DIR / "provenance.json").write_text(json.dumps(provenance, indent=2))
    print(f"Fetched {n_rows} lines -> {(OUT_DIR / (TABLE + '.data')).relative_to(REPO_ROOT)}")
    print(f"Wrote {(OUT_DIR / 'provenance.json').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
