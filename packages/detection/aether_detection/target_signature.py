"""Methane target signature for the per-column matched filter.

Three quantities live here and they are NOT interchangeable. Mixing them up is
the single most common silent bug in matched-filter implementations. Naming is
deliberate and enforced; the synthetic-plume guardrail test in
``tests/test_matched_filter.py`` verifies the math fails loudly if any of these
three are swapped or duplicated.

Quantities
----------
k(λ)   "unit absorption spectrum"
       The change in radiance per unit methane column concentration length,
       normalized by background radiance. Units: 1/(ppm·m). For EMIT this is
       the per-band finite-difference Jacobian (1/L) · ∂L/∂c computed at two
       MODTRAN methane concentration lengths (ATBD §4.2.1). Because radiance
       decreases as methane increases, k is INTRINSICALLY NEGATIVE-valued. We
       never negate it on the way in.

μ(c,λ)  "per-column mean radiance"
       The cross-track-column background radiance, μ in the ATBD. Units: same
       as the L1B radiance variable (W·m⁻²·sr⁻¹·μm⁻¹ or equivalent).

s(c,λ)  "target signature"
       The matched-filter target, s = k ⊙ μ (elementwise per band).  Units:
       radiance per ppm·m. The MF inner product s^T C⁻¹ (x - μ) divided by
       s^T C⁻¹ s yields α in ppm·m — that consistency depends on s being
       exactly k⊙μ, never k⊙μ⊙μ or +k⊙μ (sign flipped).

Sources
-------
- EMIT GHG ATBD v0.2 (Apr 2025) §4.2.1
- Thompson et al. 2015, AMT 8, 4383-4397, §2.4 Eqs. 9-12 (Beer-Lambert
  linearization of the Jacobian)
- NASA EMIT-Data-Resources Generating_Methane_Spectral_Fingerprint.ipynb
  (precomputed per-granule target file for the Permian 2022 acquisition)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt


def load_unit_absorption_spectrum(path: Path | str) -> tuple[np.ndarray, np.ndarray]:
    """Load NASA's precomputed per-granule unit absorption spectrum k(λ).

    The EMIT-Data-Resources tutorial ships a plaintext, space-separated file
    with three columns: row index, wavelength (nm), value (1/ppm·m). The
    sign of `value` is preserved verbatim — it is negative for the methane
    absorption bands by construction (radiance falls as methane rises).

    Args:
        path: Path to the per-granule target file
              (e.g. ``data/methane_tutorial/emit20220815t042838_ch4_target``).

    Returns:
        ``(wavelengths_nm, k)`` arrays of equal length.

    Notes:
        The file is granule-specific. Using a target from one granule against
        a different granule's radiance is invalid — k is column-mean-radiance
        dependent. See ``constants.PERMIAN_2022_L1B_GRANULE_UR``.
    """
    arr = np.loadtxt(path)
    if arr.ndim != 2 or arr.shape[1] < 3:
        raise ValueError(
            f"Expected at least 3 columns (idx, wavelength, value) in {path}, got shape {arr.shape}"
        )
    wavelengths_nm = arr[:, 1].astype(np.float64)
    k = arr[:, 2].astype(np.float64)
    return wavelengths_nm, k


def build_target_signature(
    unit_absorption_spectrum_k: npt.NDArray[np.float64],
    per_column_mean_radiance_mu: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Build the matched-filter target signature s = k ⊙ μ.

    This is the only correct composition. Two specific wrong compositions —
    s = k ⊙ μ ⊙ μ (doubled-μ) and s = -(k ⊙ μ) (flipped sign) — are the
    common silent bugs. The synthetic-plume guardrail test injects each of
    these as a wrong target and asserts the MF output is wrong by orders of
    magnitude (doubled-μ) or sign-inverted (flipped sign).

    Shapes:
        k has shape (n_bands,) or (n_columns, n_bands).
        μ has shape (n_columns, n_bands).
        s has shape (n_columns, n_bands).

    Both are broadcast along the columns axis so a granule-wide k applies
    correctly to per-column μ.
    """
    k = np.asarray(unit_absorption_spectrum_k, dtype=np.float64)
    mu = np.asarray(per_column_mean_radiance_mu, dtype=np.float64)
    if mu.ndim != 2:
        raise ValueError(f"μ must be 2-D (n_columns, n_bands); got shape {mu.shape}")
    if k.shape[-1] != mu.shape[-1]:
        raise ValueError(
            f"k and μ must have the same band axis length; got k={k.shape}, μ={mu.shape}"
        )
    # Elementwise product, broadcasting k across columns if k is 1-D.
    return k * mu


def select_band_indices(
    wavelengths_nm: npt.NDArray[np.float64],
    windows_nm: tuple[tuple[float, float], ...],
) -> npt.NDArray[np.intp]:
    """Return indices of bands whose center wavelength falls in any given window.

    Used to apply the EMIT MF wavelength windows (constants.MF_SPECTRAL_WINDOWS_NM)
    to a radiance cube. Inclusive endpoints, matching the EMIT-SDS operational
    interpretation of the ``--wavelength_range`` argument.
    """
    wl = np.asarray(wavelengths_nm, dtype=np.float64)
    mask = np.zeros_like(wl, dtype=bool)
    for lo, hi in windows_nm:
        mask |= (wl >= lo) & (wl <= hi)
    return np.nonzero(mask)[0]
