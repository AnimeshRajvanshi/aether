"""Sprint 6 Stage A guards: k-generation reproducibility + NASA-independence.

These pin the two things the cardinal rule depends on:
  - our k is reproducible (regenerate from committed line data + provenance ->
    identical array as the committed artifact);
  - our k generation reads NO value from NASA's per-granule target file (neither
    statically in the source, nor dynamically via any opened file path).

Self-contained: SRF arrays + geometry are read from the committed Stage A
artifacts, so the test needs no large L1B cache.
"""

from __future__ import annotations

import builtins
import json
from pathlib import Path

import numpy as np
import pytest
from aether_detection import hitran_k

_ROOT = Path(__file__).resolve().parents[3]
_KDIR = _ROOT / "stage_a_outputs" / "turkmenistan_goturdepe_2022_08_15" / "hitran_k"
# tracked JSON (the .npz is gitignored under stage_a_outputs/**/*.npz)
_KJSON = _KDIR / "hitran_k.json"
_PROV = _KDIR / "hitran_k_provenance.json"

# Tokens that would betray any read of NASA's per-granule target file.
_NASA_TOKENS = ("emit20220815t042838_ch4_target", "emit_targets", "ch4_target")


@pytest.fixture(scope="module")
def regenerated() -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Regenerate k from committed SRF + geometry, recording every opened path."""
    kj = json.loads(_KJSON.read_text())
    prov = json.loads(_PROV.read_text())
    opened: list[str] = []
    real_open = builtins.open

    def spy_open(file, *a, **k):  # type: ignore[no-untyped-def]
        opened.append(str(file))
        return real_open(file, *a, **k)

    real_loadtxt = np.loadtxt

    def spy_loadtxt(fname, *a, **k):  # type: ignore[no-untyped-def]
        opened.append(str(fname))
        return real_loadtxt(fname, *a, **k)

    builtins.open = spy_open  # type: ignore[assignment]
    np.loadtxt = spy_loadtxt  # type: ignore[assignment]
    try:
        res = hitran_k.generate_k(
            np.asarray(kj["wavelengths_nm"]),
            np.asarray(kj["fwhm_nm"]),
            solar_zenith_deg=prov["solar_zenith_deg"],
            view_zenith_deg=prov["view_zenith_deg"],
            surface_pressure_pa=prov["surface_pressure_pa"],
            surface_temperature_k=prov["surface_temperature_k"],
        )
    finally:
        builtins.open = real_open  # type: ignore[assignment]
        np.loadtxt = real_loadtxt  # type: ignore[assignment]
    return res.k, np.asarray(kj["k"]), opened


def test_k_is_reproducible(regenerated: tuple[np.ndarray, np.ndarray, list[str]]) -> None:
    fresh, committed, _ = regenerated
    # deterministic line-by-line computation -> exact agreement with the artifact
    assert np.array_equal(fresh, committed), "regenerated k differs from committed hitran_k.npz"


def test_k_generation_reads_no_nasa_file(
    regenerated: tuple[np.ndarray, np.ndarray, list[str]],
) -> None:
    _, _, opened = regenerated
    offenders = [p for p in opened if any(tok in p for tok in _NASA_TOKENS)]
    assert not offenders, f"INDEPENDENCE VIOLATION: k generation opened NASA target: {offenders}"


def test_k_source_has_no_nasa_target_reference() -> None:
    src = (Path(hitran_k.__file__)).read_text()
    for tok in _NASA_TOKENS:
        assert tok not in src, f"hitran_k.py references the NASA target token {tok!r}"


def test_k_is_negative_in_window(regenerated: tuple[np.ndarray, np.ndarray, list[str]]) -> None:
    fresh, _, _ = regenerated
    in_window = fresh[fresh != 0.0]
    assert in_window.size > 40  # ~49 MF-window bands populated
    assert np.all(in_window <= 0.0), "unit absorption must be <= 0 (radiance falls as CH4 rises)"


def test_provenance_marks_nasa_unused() -> None:
    prov = json.loads(_PROV.read_text())
    assert prov["nasa_target_used"] is False
    assert prov["hitran2020_doi"] == "10.1016/j.jqsrt.2021.107949"
    assert prov["hapi_doi"] == "10.1016/j.jqsrt.2016.03.005"
