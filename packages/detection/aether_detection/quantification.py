"""Source-rate quantification — IME on a source-connected plume mask + Varon Eq 8.

Implements Varon et al. 2018 (AMT 11, 5673-5686, doi:10.5194/amt-11-5673-2018):

  Q = U_eff · IME / L                       Eq. 8
  IME = Σ pixel mass over plume mask        Eq. 7
  L   = √(plume mask area)                  Eq. 11
  U_eff = α₁ · ln(U₁₀) + α₂                 Eq. 12 (α₁=1.0±0.1, α₂=0.6 m/s)

Mass column conversion from MF output (ppm·m) to surface mass column (kg/m²):

  n_air = p / (R · T)                       ideal gas
  mol CH₄/m² = (ppm·m) × 10⁻⁶ × n_air
  kg  CH₄/m² = (mol CH₄/m²) × M_CH₄

Pixel areas come from the ortho projection — at EPSG:4326 the per-pixel ground
size in x scales by cos(latitude), so a single number ≠ 3600 m² for the
60 m × 60 m EMIT nominal pixel; this module computes per-pixel areas
explicitly.

Nothing here is tuned to any reference value. All constants live in
``aether_detection.constants`` and trace to peer-reviewed sources.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

import numpy as np
import numpy.typing as npt

from aether_detection.constants import (
    M_AIR_KG_PER_MOL,  # noqa: F401  (kept for downstream uses)
    M_CH4_KG_PER_MOL,
    R_UNIVERSAL_J_PER_MOL_K,
    VARON2018_ALPHA_1,
    VARON2018_ALPHA_1_UNCERTAINTY,
    VARON2018_ALPHA_2,
)

# WGS84 mean meridional metres per degree of latitude. ERA5/L2B are on
# EPSG:4326 lat/lon; this constant converts the affine pixel size from
# degrees to metres along the y axis. The x axis additionally scales by
# cos(latitude_radians).
METERS_PER_DEG_LATITUDE: float = 111319.49079327357


# --------------------------------------------------------------------------- #
# Pixel areas
# --------------------------------------------------------------------------- #


def pixel_areas_m2(
    lon_centers: npt.NDArray[np.float64],
    lat_centers: npt.NDArray[np.float64],
    pixel_size_deg_x: float,
    pixel_size_deg_y: float,
) -> npt.NDArray[np.float64]:
    """Return per-pixel ground area in m² for a regular EPSG:4326 raster.

    Args:
        lon_centers: 1-D array of pixel-center longitudes (degrees).
        lat_centers: 1-D array of pixel-center latitudes (degrees).
        pixel_size_deg_x, pixel_size_deg_y: ortho transform pixel size in
            degrees (positive). For EMIT's L2B v002 grid both are ~5.42e-4°.

    Returns:
        2-D array of shape ``(len(lat_centers), len(lon_centers))`` with the
        ground area of each pixel in m². The y-direction is constant; the
        x-direction shrinks with cos(lat). At lat = 39.5° N with EMIT's
        pixel size, the area is ~2 800 m², not 3 600 m².
    """
    dy_m = pixel_size_deg_y * METERS_PER_DEG_LATITUDE
    dx_m_per_lat = pixel_size_deg_x * METERS_PER_DEG_LATITUDE * np.cos(
        np.radians(lat_centers)
    )
    return np.outer(dx_m_per_lat * dy_m, np.ones_like(lon_centers))


# --------------------------------------------------------------------------- #
# Mass column
# --------------------------------------------------------------------------- #


def n_air_mol_per_m3(p_pa: float, t_k: float) -> float:
    """Ideal-gas molar number density of air. p in Pa, T in K → mol/m³."""
    if p_pa <= 0 or t_k <= 0:
        raise ValueError(f"non-physical p={p_pa} Pa or T={t_k} K")
    return p_pa / (R_UNIVERSAL_J_PER_MOL_K * t_k)


def ppm_m_to_kg_m2(
    enh_ppm_m: npt.NDArray[np.float64],
    n_air_mol_m3: float,
    m_ch4_kg_per_mol: float = M_CH4_KG_PER_MOL,
) -> npt.NDArray[np.float64]:
    """Convert a methane column enhancement field from ppm·m to kg/m²."""
    return enh_ppm_m * 1.0e-6 * n_air_mol_m3 * m_ch4_kg_per_mol


# --------------------------------------------------------------------------- #
# IME on a mask
# --------------------------------------------------------------------------- #


def ime_kg(
    enh_ppm_m: npt.NDArray[np.float64],
    plume_mask: npt.NDArray[np.bool_],
    pixel_areas: npt.NDArray[np.float64],
    n_air_mol_m3: float,
    m_ch4_kg_per_mol: float = M_CH4_KG_PER_MOL,
) -> float:
    """Integrated mass enhancement over a boolean plume mask. Returns kg.

    Equivalent to Varon Eq. 7: IME = Σⱼ Δⱼ · Aⱼ over plume mask pixels,
    where Δⱼ is the column mass enhancement in kg/m² and Aⱼ is the pixel
    area in m². Pixels outside the mask, NaN, or non-finite contribute zero.
    """
    if enh_ppm_m.shape != plume_mask.shape or enh_ppm_m.shape != pixel_areas.shape:
        raise ValueError(
            "enh_ppm_m, plume_mask, pixel_areas must share shape; "
            f"got {enh_ppm_m.shape}, {plume_mask.shape}, {pixel_areas.shape}"
        )
    finite = np.isfinite(enh_ppm_m)
    take = plume_mask & finite
    if not np.any(take):
        return 0.0
    mass_col = ppm_m_to_kg_m2(enh_ppm_m[take], n_air_mol_m3, m_ch4_kg_per_mol)
    return float((mass_col * pixel_areas[take]).sum())


def plume_area_m2(
    plume_mask: npt.NDArray[np.bool_],
    pixel_areas: npt.NDArray[np.float64],
) -> float:
    """Sum of per-pixel ground areas over the plume mask, in m². Varon's A_M."""
    if plume_mask.shape != pixel_areas.shape:
        raise ValueError(
            f"plume_mask shape {plume_mask.shape} != pixel_areas shape {pixel_areas.shape}"
        )
    return float(pixel_areas[plume_mask].sum())


def plume_length_m(plume_mask_area_m2: float) -> float:
    """Characteristic plume length L = sqrt(A_mask). Varon 2018 Eq. 11."""
    if plume_mask_area_m2 < 0:
        raise ValueError(f"plume area must be non-negative; got {plume_mask_area_m2}")
    return float(np.sqrt(plume_mask_area_m2))


# --------------------------------------------------------------------------- #
# Wind: Varon Eq. 12
# --------------------------------------------------------------------------- #


def u_eff_varon(
    u10_ms: float,
    alpha_1: float = VARON2018_ALPHA_1,
    alpha_2: float = VARON2018_ALPHA_2,
) -> float:
    """Effective wind speed via Varon 2018 Eq. 12.

    Returns U_eff = α₁ · ln(U₁₀) + α₂ in m/s. Valid for U₁₀ ≥ ~2 m/s; below
    that the parameterisation degrades — see Varon 2018 §5.2. Raises on
    non-positive U₁₀ (the natural log is undefined).
    """
    if u10_ms <= 0:
        raise ValueError(f"u10 must be > 0 m/s for Varon Eq. 12; got {u10_ms}")
    return float(alpha_1 * np.log(u10_ms) + alpha_2)


# --------------------------------------------------------------------------- #
# Q
# --------------------------------------------------------------------------- #

KG_PER_SECOND_TO_TONNES_PER_HOUR: float = 3.6


def q_kg_per_second(
    ime_kg_value: float, u_eff_ms: float, plume_length_m_value: float
) -> float:
    """Source rate Q = U_eff · IME / L (Varon Eq. 8). Returns kg/s."""
    if plume_length_m_value <= 0:
        raise ValueError(f"plume_length_m must be > 0; got {plume_length_m_value}")
    return float(u_eff_ms * ime_kg_value / plume_length_m_value)


def kg_s_to_tonnes_per_hour(q_kg_s: float) -> float:
    """Convert kg/s → t/hr. 1 kg/s × 3600 s/hr ÷ 1000 kg/t = 3.6 t/hr."""
    return q_kg_s * KG_PER_SECOND_TO_TONNES_PER_HOUR


# --------------------------------------------------------------------------- #
# Uncertainty propagation
# --------------------------------------------------------------------------- #


class WindUncertainty(NamedTuple):
    """Decomposition of the wind-related fractional uncertainty on Q.

    All quantities are fractional (i.e. σ_Q / Q components) at the central
    α₁, α₂, and U₁₀ values supplied by the caller. They combine in quadrature
    into ``total``.
    """

    alpha1_term: float
    u10_term: float
    total: float


def wind_uncertainty_on_q(
    u10_ms: float,
    alpha_1: float = VARON2018_ALPHA_1,
    alpha_2: float = VARON2018_ALPHA_2,
    alpha_1_sigma: float = VARON2018_ALPHA_1_UNCERTAINTY,
    u10_sigma_ms: float = 1.6,
) -> WindUncertainty:
    """Linear-propagation wind contribution to σ_Q / Q.

    Q ∝ U_eff, so σ_Q / Q = σ_U_eff / U_eff. With
    U_eff(α₁, U₁₀) = α₁ ln(U₁₀) + α₂:

      ∂U_eff/∂α₁  = ln(U₁₀)
      ∂U_eff/∂U₁₀ = α₁ / U₁₀

    The default ``u10_sigma_ms = 1.6`` comes from Varon 2018 §7 (GEOS-FP vs
    MesoWest illustrative comparison). Callers should override with a
    representativeness estimate informed by the actual ERA5 hour-distance.
    """
    if u10_ms <= 0:
        raise ValueError(f"u10 must be > 0 for derivatives; got {u10_ms}")
    u_eff = u_eff_varon(u10_ms, alpha_1, alpha_2)
    if u_eff <= 0:
        raise ValueError(
            f"U_eff computed as {u_eff} ≤ 0; Varon parameterisation invalid below ~U10=2 m/s"
        )
    du_eff_da1 = np.log(u10_ms)
    du_eff_du10 = alpha_1 / u10_ms
    sigma_from_a1 = abs(du_eff_da1) * alpha_1_sigma
    sigma_from_u10 = abs(du_eff_du10) * u10_sigma_ms
    sigma_u_eff = float(np.sqrt(sigma_from_a1 ** 2 + sigma_from_u10 ** 2))
    return WindUncertainty(
        alpha1_term=float(sigma_from_a1 / u_eff),
        u10_term=float(sigma_from_u10 / u_eff),
        total=float(sigma_u_eff / u_eff),
    )


# --------------------------------------------------------------------------- #
# Convenience aggregator
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class IMEResult:
    """Output of :func:`quantify_plume`.

    All numerical fields trace to a documented source.
    """

    ime_kg: float
    plume_area_m2: float
    plume_length_m: float
    u10_ms: float
    u_eff_ms: float
    q_kg_per_s: float
    q_tonnes_per_hr: float
    # Wind-only fractional uncertainty (linearised). The remaining terms —
    # enhancement calibration and plume-mask sensitivity — are computed and
    # carried by the Stage B driver, NOT here, because they require running
    # the segmentation at multiple thresholds and comparing to NASA's L2B.
    wind_fractional_uncertainty: WindUncertainty = field(
        default_factory=lambda: WindUncertainty(0.0, 0.0, 0.0)
    )


def quantify_plume(
    enh_ppm_m: npt.NDArray[np.float64],
    plume_mask: npt.NDArray[np.bool_],
    pixel_areas: npt.NDArray[np.float64],
    n_air_mol_m3: float,
    u10_ms: float,
    *,
    alpha_1: float = VARON2018_ALPHA_1,
    alpha_2: float = VARON2018_ALPHA_2,
    alpha_1_sigma: float = VARON2018_ALPHA_1_UNCERTAINTY,
    u10_sigma_ms: float = 1.6,
) -> IMEResult:
    """Compute IME and Q on a plume mask, with wind-only linearised uncertainty.

    See module docstring for the full Varon 2018 reference chain. Pixel
    areas must be precomputed via :func:`pixel_areas_m2`; n_air via
    :func:`n_air_mol_per_m3`.
    """
    if enh_ppm_m.shape != plume_mask.shape or enh_ppm_m.shape != pixel_areas.shape:
        raise ValueError(
            "shapes mismatch: enh="
            f"{enh_ppm_m.shape}, mask={plume_mask.shape}, areas={pixel_areas.shape}"
        )
    ime = ime_kg(enh_ppm_m, plume_mask, pixel_areas, n_air_mol_m3)
    a_m = plume_area_m2(plume_mask, pixel_areas)
    plume_l = plume_length_m(a_m)
    u_eff = u_eff_varon(u10_ms, alpha_1, alpha_2)
    if plume_l <= 0:
        raise ValueError("plume mask has zero area; Q is undefined")
    q_kg_s = q_kg_per_second(ime, u_eff, plume_l)
    q_t_hr = kg_s_to_tonnes_per_hour(q_kg_s)
    wind_unc = wind_uncertainty_on_q(
        u10_ms, alpha_1=alpha_1, alpha_2=alpha_2,
        alpha_1_sigma=alpha_1_sigma, u10_sigma_ms=u10_sigma_ms,
    )
    return IMEResult(
        ime_kg=ime, plume_area_m2=a_m, plume_length_m=plume_l,
        u10_ms=u10_ms, u_eff_ms=u_eff,
        q_kg_per_s=q_kg_s, q_tonnes_per_hr=q_t_hr,
        wind_fractional_uncertainty=wind_unc,
    )
