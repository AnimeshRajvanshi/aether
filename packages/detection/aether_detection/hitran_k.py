"""Generate an independent methane unit-absorption spectrum k from HITRAN.

This is the Sprint 6 independence work: compute the matched-filter unit absorption
spectrum ``k`` (1/(ppm·m)) from HITRAN line-by-line spectroscopy + an atmospheric
path model + EMIT's spectral response — with ZERO values read from NASA's
per-granule target file. NASA's file is a validation cross-check only and is never
touched in this module.

Recipe (every approximation documented):
  1. Line data: HITRAN2020 CH4 (HAPI), fetched over the Sprint 2 window and cached
     (scripts/fetch_hitran_ch4.py). Voigt line shape (HAPI ``absorptionCoefficient_
     Voigt``) gives the air-broadened absorption cross-section sigma(nu) [cm^2/molec],
     isotopologue-abundance weighted, at the near-surface enhancement layer's P, T.
  2. Two-way path: the unit enhancement is a near-surface ppm·m of CH4; its slant
     optical depth uses the air-mass factor AMF = sec(SZA) + sec(VZA) from the
     granule's own geometry (downwelling solar + upwelling to-sensor).
  3. Unit absorption (Beer-Lambert linearization, the EMIT/Thompson-2015 definition
     k = d(ln L)/dc): k_hires(nu) = -AMF * sigma(nu) * N_per_ppmm, intrinsically
     negative (radiance falls as methane rises). N_per_ppmm is the excess CH4 column
     [molec/cm^2] per ppm·m at the surface layer's number density.
  4. Convolve k_hires to EMIT bands with a per-band Gaussian SRF built from the
     granule's own wavelength + FWHM arrays (sigma = FWHM / 2.355).

The result is our independent k on EMIT's spectral grid. The absolute scale (AMF,
N_per_ppmm) does not affect the Stage A spectral-SHAPE validation (Pearson is
scale-invariant); it is retained because Stage B needs the physical amplitude.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

warnings.filterwarnings("ignore")  # HAPI emits regex SyntaxWarnings on import
import hapi  # noqa: E402

from aether_detection.constants import MF_SPECTRAL_WINDOWS_NM  # noqa: E402

_RESOURCES = Path(__file__).resolve().parent / "resources" / "hitran"
_TABLE = "CH4_win"

# Methane (molecule 6) main isotopologues; abundance weighting is HAPI's default.
_CH4_COMPONENTS = [(6, 1), (6, 2), (6, 3), (6, 4)]

# Boltzmann constant (CODATA), for n_air = P / (k_B T).
_K_B = 1.380649e-23  # J/K

# Hi-res spectral step for the Voigt cross-section (cm^-1). Pressure-broadened CH4
# HWHM at 1 atm is ~0.05-0.07 cm^-1, so 0.01 gives several samples per line core.
_WAVENUMBER_STEP_CM = 0.01


@dataclass
class KResult:
    """Our independent k plus the hi-res spectrum and full provenance."""

    wavelengths_nm: npt.NDArray[np.float64]  # EMIT band centers (granule grid)
    k: npt.NDArray[np.float64]  # our k, 1/(ppm·m), on the EMIT grid (<=0 in-window)
    hires_nm: npt.NDArray[np.float64]  # hi-res wavelength grid (nm, ascending)
    hires_k: npt.NDArray[np.float64]  # hi-res k, 1/(ppm·m)
    in_window_mask: npt.NDArray[np.bool_]  # EMIT bands inside the MF window
    provenance: dict[str, Any] = field(default_factory=dict)


def _air_number_density_cm3(pressure_pa: float, temperature_k: float) -> float:
    """n_air [molecules / cm^3] from the ideal gas law."""
    n_m3 = pressure_pa / (_K_B * temperature_k)
    return n_m3 * 1.0e-6


def _excess_ch4_column_per_ppmm(pressure_pa: float, temperature_k: float) -> float:
    """Excess CH4 column [molec/cm^2] per ppm·m enhancement at the surface layer.

    1 ppm·m = 1e-6 (mol/mol) * 1 m path -> N = 1e-6 * n_air[molec/m^3] * 1 m,
    converted to molec/cm^2 (x 1e-4).
    """
    n_air_m3 = pressure_pa / (_K_B * temperature_k)
    return 1.0e-6 * n_air_m3 * 1.0e-4  # molec/cm^2 per ppm·m


def _voigt_cross_section(
    pressure_pa: float, temperature_k: float, numin: float, numax: float
) -> tuple[np.ndarray, np.ndarray]:
    """Air-broadened CH4 Voigt cross-section sigma(nu) [cm^2/molec] from HITRAN."""
    hapi.db_begin(str(_RESOURCES))
    nu, xsec = hapi.absorptionCoefficient_Voigt(
        Components=_CH4_COMPONENTS,
        SourceTables=[_TABLE],
        Environment={"p": pressure_pa / 101325.0, "T": temperature_k},  # p in atm
        WavenumberRange=(numin, numax),
        WavenumberStep=_WAVENUMBER_STEP_CM,
        HITRAN_units=True,  # cm^2/molecule
        Diluent={"air": 1.0},
    )
    return np.asarray(nu, dtype=np.float64), np.asarray(xsec, dtype=np.float64)


def _convolve_to_emit(
    hires_nm: np.ndarray,
    hires_k: np.ndarray,
    band_centers_nm: np.ndarray,
    band_fwhm_nm: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-band Gaussian-SRF convolution onto the EMIT grid.

    Returns (k_emit, in_window_mask). Bands whose center lies within the hi-res
    coverage get the SRF-weighted integral of k_hires; bands outside get 0 (they
    are not used by the matched filter).
    """
    k_emit = np.zeros_like(band_centers_nm, dtype=np.float64)
    in_cov = (band_centers_nm >= hires_nm.min()) & (band_centers_nm <= hires_nm.max())
    for i in np.nonzero(in_cov)[0]:
        sigma = band_fwhm_nm[i] / 2.3548200450309493  # FWHM -> Gaussian sigma
        lo, hi = band_centers_nm[i] - 4.0 * sigma, band_centers_nm[i] + 4.0 * sigma
        sel = (hires_nm >= lo) & (hires_nm <= hi)
        if not np.any(sel):
            continue
        w = np.exp(-0.5 * ((hires_nm[sel] - band_centers_nm[i]) / sigma) ** 2)
        # trapezoidal integration in wavelength (hi-res grid is non-uniform in nm)
        num = np.trapezoid(w * hires_k[sel], hires_nm[sel])
        den = np.trapezoid(w, hires_nm[sel])
        if den != 0.0:
            k_emit[i] = num / den
    return k_emit, in_cov


def generate_k(
    band_centers_nm: npt.NDArray[np.float64],
    band_fwhm_nm: npt.NDArray[np.float64],
    *,
    solar_zenith_deg: float,
    view_zenith_deg: float,
    surface_pressure_pa: float,
    surface_temperature_k: float,
    ch4_background_ppm: float = 1.87,
) -> KResult:
    """Compute our independent EMIT-grid methane unit absorption spectrum k.

    Args:
        band_centers_nm, band_fwhm_nm: the granule's own SRF arrays (length n_bands).
        solar_zenith_deg, view_zenith_deg: the granule's actual geometry (OBS cube).
        surface_pressure_pa, surface_temperature_k: near-surface enhancement-layer
            state (the scene's ERA5 surface values; our own input, never NASA's).
        ch4_background_ppm: background CH4 VMR, recorded for provenance (the linear
            unit absorption is set by the surface cross-section, not the background
            column; see module docstring).

    Returns:
        KResult with k on the EMIT grid plus the hi-res spectrum and provenance.
    """
    band_centers_nm = np.asarray(band_centers_nm, dtype=np.float64)
    band_fwhm_nm = np.asarray(band_fwhm_nm, dtype=np.float64)

    lo_nm = min(w[0] for w in MF_SPECTRAL_WINDOWS_NM)
    hi_nm = max(w[1] for w in MF_SPECTRAL_WINDOWS_NM)
    # cross-section over a margin-padded wavenumber range (match the cached lines)
    numin = 1.0e7 / hi_nm - 60.0
    numax = 1.0e7 / lo_nm + 60.0

    nu, xsec = _voigt_cross_section(surface_pressure_pa, surface_temperature_k, numin, numax)

    amf = 1.0 / math.cos(math.radians(solar_zenith_deg)) + 1.0 / math.cos(
        math.radians(view_zenith_deg)
    )
    n_per_ppmm = _excess_ch4_column_per_ppmm(surface_pressure_pa, surface_temperature_k)

    # Beer-Lambert linear unit absorption: k = d(ln L)/dc = -AMF * sigma * N_per_ppmm
    hires_k_nu = -amf * xsec * n_per_ppmm  # 1/(ppm·m), on the nu grid

    # nu (cm^-1, ascending) -> wavelength (nm); reorder ascending in nm
    hires_nm = 1.0e7 / nu
    order = np.argsort(hires_nm)
    hires_nm = hires_nm[order]
    hires_k = hires_k_nu[order]

    k_emit, in_window = _convolve_to_emit(hires_nm, hires_k, band_centers_nm, band_fwhm_nm)

    provenance = {
        "method": "HITRAN2020 line-by-line (HAPI) Voigt cross-section, "
        "Beer-Lambert linear unit absorption, Gaussian-SRF convolved to EMIT",
        "hitran2020_doi": "10.1016/j.jqsrt.2021.107949",
        "hapi_doi": "10.1016/j.jqsrt.2016.03.005",
        "line_table": _TABLE,
        "isotopologues": _CH4_COMPONENTS,
        "wavenumber_range_cm": [numin, numax],
        "wavenumber_step_cm": _WAVENUMBER_STEP_CM,
        "solar_zenith_deg": solar_zenith_deg,
        "view_zenith_deg": view_zenith_deg,
        "air_mass_factor": amf,
        "surface_pressure_pa": surface_pressure_pa,
        "surface_temperature_k": surface_temperature_k,
        "n_air_cm3": _air_number_density_cm3(surface_pressure_pa, surface_temperature_k),
        "excess_ch4_column_per_ppmm_molec_cm2": n_per_ppmm,
        "ch4_background_ppm": ch4_background_ppm,
        "n_emit_bands": int(band_centers_nm.size),
        "n_in_window_bands": int(in_window.sum()),
        "window_nm": [lo_nm, hi_nm],
        "nasa_target_used": False,
    }
    return KResult(
        wavelengths_nm=band_centers_nm,
        k=k_emit,
        hires_nm=hires_nm,
        hires_k=hires_k,
        in_window_mask=in_window,
        provenance=provenance,
    )
