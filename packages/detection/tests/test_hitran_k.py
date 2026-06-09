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


# --- Stage B: guard the committed end-to-end report (CI-safe; reads the artifact) ---
_STAGE_B = _KDIR / "hitran_k_stage_b_report.json"


def test_stage_b_scaling_is_forward_not_reverse_fit() -> None:
    rep = json.loads(_STAGE_B.read_text())
    # the forward unit-chain scale, NOT chosen to match 27.1 t/hr
    assert rep["ppm_scaling_factor_forward"] == 1.0
    assert "not reverse-fit" in rep["scaling_chain"].lower()


def test_stage_b_divergence_recorded_honestly() -> None:
    rep = json.loads(_STAGE_B.read_text())
    # the report must surface (not hide) the Pearson drop and the calibration shift
    assert rep["pearson_in_bbox"] < rep["sprint2_pearson_in_bbox"]
    assert rep["amplitude_vs_nasa_l2b_over_cc"] != rep["sprint2_bias_factor"]
    # ours-cal Q is reported as-is (falls out of the forward scale), not patched to 27.1
    assert abs(rep["q_ours_cal_t_hr"] - rep["sprint2_q_ours_cal_t_hr"]) > 1.0


# --- v2: saturation-aware k (finite-enhancement regression) -------------------
_KSAT = _KDIR / "hitran_k_sat.json"
_PROV_SAT = _KDIR / "hitran_k_sat_provenance.json"
_V2 = _KDIR / "hitran_k_v2_report.json"


@pytest.fixture(scope="module")
def regenerated_sat() -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Regenerate the saturation-aware k, recording every opened path."""
    kj = json.loads(_KSAT.read_text())
    prov = json.loads(_PROV_SAT.read_text())
    opened: list[str] = []
    real_open = builtins.open

    def spy_open(file, *a, **k):  # type: ignore[no-untyped-def]
        opened.append(str(file))
        return real_open(file, *a, **k)

    builtins.open = spy_open  # type: ignore[assignment]
    try:
        res = hitran_k.generate_k_regression(
            np.asarray(kj["wavelengths_nm"]),
            np.asarray(kj["fwhm_nm"]),
            solar_zenith_deg=prov["solar_zenith_deg"],
            view_zenith_deg=prov["view_zenith_deg"],
            surface_pressure_pa=prov["surface_pressure_pa"],
            surface_temperature_k=prov["surface_temperature_k"],
            c_max_ppm_m=prov["enhancement_ladder_ppm_m"][1],
            n_c=prov["enhancement_ladder_n"],
        )
    finally:
        builtins.open = real_open  # type: ignore[assignment]
    return res.k, np.asarray(kj["k"]), opened


def test_sat_k_is_reproducible(regenerated_sat: tuple[np.ndarray, np.ndarray, list[str]]) -> None:
    fresh, committed, _ = regenerated_sat
    assert np.array_equal(fresh, committed), "regenerated saturation k != committed sat json"


def test_sat_k_reads_no_nasa_file(
    regenerated_sat: tuple[np.ndarray, np.ndarray, list[str]],
) -> None:
    _, _, opened = regenerated_sat
    offenders = [p for p in opened if any(tok in p for tok in _NASA_TOKENS)]
    assert not offenders, f"INDEPENDENCE VIOLATION: saturation k opened NASA target: {offenders}"


def test_sat_k_negative_in_window(
    regenerated_sat: tuple[np.ndarray, np.ndarray, list[str]],
) -> None:
    fresh, _, _ = regenerated_sat
    inw = fresh[fresh != 0.0]
    assert inw.size > 40 and np.all(inw <= 0.0)


def test_v2_restores_fidelity_and_reproduces_overamplitude() -> None:
    rep = json.loads(_V2.read_text())
    # (a) shape recovers past the linear 0.93
    assert rep["shape_pearson_r_vs_nasa"] > 0.98
    # (b) end-to-end fidelity restored: much closer to Sprint 2 than v1 linear was
    assert rep["pearson_in_bbox"] > 0.70
    assert rep["pearson_in_bbox"] > rep["v1_linear_pearson_in_bbox"]
    # (c) the +1.66x over-amplitude is reproduced independently (not the v1 0.79x)
    assert rep["amplitude_vs_nasa_l2b_over_cc"] > 1.0
    # forward scale unchanged; NASA-anchored flux stays ~16 t/hr (not reverse-fit)
    assert rep["ppm_scaling_factor_forward"] == 1.0
    assert abs(rep["q_nasa_cal_t_hr"] - rep["sprint2_q_nasa_cal_t_hr"]) < 1.5
    assert rep["prov_nasa_target_used"] is False
