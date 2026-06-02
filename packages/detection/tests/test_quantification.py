"""Tests for the IME quantification module."""

from __future__ import annotations

import numpy as np
import pytest
from aether_detection import constants, quantification

# --------------------------------------------------------------------------- #
# Pixel areas
# --------------------------------------------------------------------------- #


def test_pixel_areas_at_equator_match_naive_calculation() -> None:
    """At the equator cos(lat) = 1, so dx_m × dy_m at EMIT's pixel size
    should be ~60 m × ~60 m = ~3 600 m². This is the only latitude where
    the assumed-3600-m² convention is approximately correct."""
    lon_c = np.linspace(0, 1, 10)
    lat_c = np.array([0.0])  # equator
    areas = quantification.pixel_areas_m2(
        lon_c, lat_c, pixel_size_deg_x=5.422e-4, pixel_size_deg_y=5.422e-4
    )
    assert areas.shape == (1, 10)
    expected = (5.422e-4 * quantification.METERS_PER_DEG_LATITUDE) ** 2
    np.testing.assert_allclose(areas, expected, rtol=1e-10)


def test_pixel_areas_at_lat_39p5_are_smaller_than_3600() -> None:
    """At lat 39.5 N the EMIT-grid pixel area is ~2 800 m², NOT 3 600.
    Using 3 600 m² would over-estimate IME by ~30%."""
    lat_c = np.array([39.5])
    lon_c = np.array([0.0])
    areas = quantification.pixel_areas_m2(
        lon_c, lat_c, pixel_size_deg_x=5.422e-4, pixel_size_deg_y=5.422e-4
    )
    # Expected:
    #   dy = 5.422e-4 * 111319.49 = 60.36 m
    #   dx = 60.36 * cos(39.5°) = 60.36 * 0.7716 = 46.57 m
    #   area = 60.36 * 46.57 ≈ 2811 m²
    expected = 60.36 * 60.36 * np.cos(np.radians(39.5))
    np.testing.assert_allclose(areas[0, 0], expected, rtol=2e-3)
    assert areas[0, 0] < 3600.0  # the documented anti-pattern
    assert areas[0, 0] > 2700.0


# --------------------------------------------------------------------------- #
# n_air and ppm·m → kg/m²
# --------------------------------------------------------------------------- #


def test_n_air_at_standard_conditions() -> None:
    """Loschmidt's number, ~44.6 mol/m³ at 1 atm and 273.15 K."""
    n = quantification.n_air_mol_per_m3(p_pa=101325.0, t_k=273.15)
    np.testing.assert_allclose(n, 44.62, atol=0.05)


def test_n_air_rejects_nonphysical_inputs() -> None:
    with pytest.raises(ValueError, match="non-physical"):
        quantification.n_air_mol_per_m3(p_pa=0.0, t_k=300.0)
    with pytest.raises(ValueError, match="non-physical"):
        quantification.n_air_mol_per_m3(p_pa=101325.0, t_k=0.0)


def test_ppm_m_to_kg_m2_textbook_value_at_stp() -> None:
    """1 ppm·m of CH4 at STP → ~7.16e-7 kg/m².

    Verified: n_air(STP) = 44.62 mol/m³; 1 ppm·m × 1e-6 × 44.62
    = 4.462e-5 mol/m²; × 0.01604 kg/mol = 7.16e-7 kg/m².
    """
    n_air = quantification.n_air_mol_per_m3(p_pa=101325.0, t_k=273.15)
    out = quantification.ppm_m_to_kg_m2(np.array(1.0), n_air)
    np.testing.assert_allclose(out, 7.16e-7, rtol=1e-2)


# --------------------------------------------------------------------------- #
# IME on a synthetic plume — round-trip a known total mass
# --------------------------------------------------------------------------- #


def test_ime_recovers_known_synthetic_mass() -> None:
    """Inject a flat-top plume of known column enhancement over N pixels of
    known per-pixel area, and verify IME = (mass per pixel) × N."""
    n_rows, n_cols = 50, 60
    enh = np.zeros((n_rows, n_cols))
    plume_value_ppmm = 500.0
    plume_mask = np.zeros_like(enh, dtype=bool)
    plume_mask[10:30, 20:40] = True  # 20 × 20 = 400 pixels
    enh[plume_mask] = plume_value_ppmm
    # Use a uniform area for clarity
    pixel_areas = np.full_like(enh, 3000.0)
    n_air = quantification.n_air_mol_per_m3(101325.0, 295.0)  # ~41.3 mol/m³

    ime = quantification.ime_kg(enh, plume_mask, pixel_areas, n_air)

    # Hand-compute the expected mass:
    mass_per_m2 = quantification.ppm_m_to_kg_m2(plume_value_ppmm, n_air)
    expected = mass_per_m2 * 3000.0 * 400
    np.testing.assert_allclose(ime, expected, rtol=1e-10)


def test_ime_ignores_off_mask_and_nan_pixels() -> None:
    enh = np.ones((20, 20)) * 100.0
    mask = np.zeros_like(enh, dtype=bool)
    mask[5:15, 5:15] = True
    enh[7, 8] = np.nan          # NaN inside mask — must skip
    enh[0, 0] = 99999.0          # outside mask — must skip
    areas = np.full_like(enh, 2500.0)
    n_air = quantification.n_air_mol_per_m3(101325.0, 295.0)
    ime = quantification.ime_kg(enh, mask, areas, n_air)
    mass_per = quantification.ppm_m_to_kg_m2(100.0, n_air) * 2500.0
    # 10×10 mask − 1 NaN = 99 contributing pixels
    np.testing.assert_allclose(ime, 99 * mass_per, rtol=1e-10)


# --------------------------------------------------------------------------- #
# U_eff (Varon Eq. 12)
# --------------------------------------------------------------------------- #


def test_u_eff_at_u10_5ms_with_central_coefficients() -> None:
    """For U10 = 5 m/s, α1=1.0, α2=0.6 → U_eff = ln(5) + 0.6 ≈ 2.209 m/s."""
    u_eff = quantification.u_eff_varon(5.0)
    np.testing.assert_allclose(u_eff, np.log(5.0) + 0.6, rtol=1e-12)


def test_u_eff_rejects_nonpositive_u10() -> None:
    with pytest.raises(ValueError, match="must be > 0"):
        quantification.u_eff_varon(0.0)
    with pytest.raises(ValueError, match="must be > 0"):
        quantification.u_eff_varon(-1.0)


# --------------------------------------------------------------------------- #
# Q (Varon Eq. 8) — end-to-end synthetic round-trip
# --------------------------------------------------------------------------- #


def test_quantify_plume_end_to_end() -> None:
    """Build a synthetic plume with hand-known IME, plume area, U10. Verify
    quantify_plume reproduces Q = U_eff · IME / L precisely."""
    n_rows, n_cols = 60, 80
    enh = np.zeros((n_rows, n_cols))
    plume_mask = np.zeros_like(enh, dtype=bool)
    plume_mask[10:30, 30:50] = True   # 400 pixels
    enh[plume_mask] = 1000.0
    pixel_areas = np.full_like(enh, 2800.0)
    n_air = quantification.n_air_mol_per_m3(101325.0, 295.0)
    u10 = 5.0

    out = quantification.quantify_plume(enh, plume_mask, pixel_areas, n_air, u10)

    # Hand-recompute
    mass_per_m2 = quantification.ppm_m_to_kg_m2(1000.0, n_air)
    expected_ime = mass_per_m2 * 2800.0 * 400
    expected_area = 2800.0 * 400
    expected_plume_l = np.sqrt(expected_area)
    expected_u_eff = np.log(u10) + 0.6
    expected_q_kg_s = expected_u_eff * expected_ime / expected_plume_l
    expected_q_t_hr = expected_q_kg_s * 3.6

    np.testing.assert_allclose(out.ime_kg, expected_ime, rtol=1e-12)
    np.testing.assert_allclose(out.plume_area_m2, expected_area, rtol=1e-12)
    np.testing.assert_allclose(out.plume_length_m, expected_plume_l, rtol=1e-12)
    np.testing.assert_allclose(out.u_eff_ms, expected_u_eff, rtol=1e-12)
    np.testing.assert_allclose(out.q_kg_per_s, expected_q_kg_s, rtol=1e-12)
    np.testing.assert_allclose(out.q_tonnes_per_hr, expected_q_t_hr, rtol=1e-12)


def test_wind_uncertainty_components_match_analytic_derivatives() -> None:
    """At U10=5 m/s with default α1, α2:
       ∂U_eff/∂α1  = ln(5) = 1.609
       ∂U_eff/∂U10 = 1.0/5 = 0.2
       σ_α1 = 0.1 → σ_U_eff_from_α1 = 0.161
       σ_U10 = 1.6 → σ_U_eff_from_U10 = 0.32
       U_eff = ln(5) + 0.6 = 2.209
       Total fractional = sqrt(0.161^2 + 0.32^2) / 2.209 = 0.162
    """
    wu = quantification.wind_uncertainty_on_q(5.0)
    np.testing.assert_allclose(wu.alpha1_term, 0.161 / 2.209, rtol=1e-3)
    np.testing.assert_allclose(wu.u10_term, 0.32 / 2.209, rtol=1e-3)
    np.testing.assert_allclose(wu.total, np.sqrt(0.161 ** 2 + 0.32 ** 2) / 2.209, rtol=1e-3)


def test_quantify_plume_rejects_zero_area_mask() -> None:
    enh = np.zeros((10, 10))
    empty_mask = np.zeros_like(enh, dtype=bool)
    areas = np.full_like(enh, 2800.0)
    n_air = quantification.n_air_mol_per_m3(101325.0, 295.0)
    with pytest.raises(ValueError, match="zero area"):
        quantification.quantify_plume(enh, empty_mask, areas, n_air, u10_ms=5.0)


def test_constants_are_from_documented_sources() -> None:
    """Sanity check the imported constants are present and correct."""
    assert constants.M_CH4_KG_PER_MOL == 0.01604
    assert constants.VARON2018_ALPHA_1 == 1.0
    assert constants.VARON2018_ALPHA_2 == 0.6
    assert constants.VARON2018_ALPHA_1_UNCERTAINTY == 0.1
