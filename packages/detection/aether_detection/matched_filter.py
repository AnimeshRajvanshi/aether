"""Per-column adaptive matched filter for methane enhancement retrieval.

Implements the EMIT operational matched filter as documented in:
- EMIT GHG ATBD v0.2 (Apr 2025) §4.2.1
  ``MF = sᵀ C⁻¹ (x − μ) / (sᵀ C⁻¹ s)``
- Thompson et al. 2015, AMT 8, 4383-4397, §2.3-2.4 (original formulation)

Output units are ppm·m (matching the unit absorption spectrum k in 1/(ppm·m)
multiplied by μ in radiance units, giving s in radiance per ppm·m).

Per-column statistics are essential: EMIT is push-broom; each cross-track
detector has its own response. Computing μ and Σ over the whole scene produces
cross-track stripes that the matched filter cannot remove.

This module does not orthorectify. It operates in raw sensor geometry (the
native L1B layout) — the GLT-based reprojection happens downstream in the
data spine after we have a per-pixel enhancement raster.

Per-column covariance regularisation uses a fixed diagonal-loading shrinkage
α = :data:`MF_SHRINKAGE_ALPHA` (1e-9 per EMIT GHG ATBD §4.2.1). A LOOCV port
of NASA's `parallel_mf.py` shrinkage selector is available behind the opt-in
``shrinkage_alpha="loocv"`` but is **NOT** the production default: on
uncentered EMIT radiance it over-shrinks the bulk and does not suppress the
blob artefact. See :func:`fit_looshrinkage_alpha` and the constants module.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from aether_detection.constants import (
    MF_LOOCV_ALPHA_LOG10_MAX,
    MF_LOOCV_ALPHA_LOG10_MIN,
    MF_LOOCV_ALPHA_LOG10_STEP,
    MF_LOOCV_STABILITY_SCALING,
    MF_PPM_SCALING_FACTOR,
    MF_SHRINKAGE_ALPHA,
    MF_SPECTRAL_WINDOWS_NM,
)
from aether_detection.target_signature import (
    build_target_signature,
    select_band_indices,
)

LOOCV_SENTINEL = "loocv"


def _default_alpha_grid() -> npt.NDArray[np.float64]:
    """Build the LOOCV candidate-α grid from the constants module."""
    return 10.0 ** np.arange(
        MF_LOOCV_ALPHA_LOG10_MIN,
        MF_LOOCV_ALPHA_LOG10_MAX + MF_LOOCV_ALPHA_LOG10_STEP,
        MF_LOOCV_ALPHA_LOG10_STEP,
    )


def fit_looshrinkage_alpha(
    column_radiance: npt.NDArray[np.float64],
    *,
    alpha_grid: npt.NDArray[np.float64] | None = None,
    stability_scaling: float = MF_LOOCV_STABILITY_SCALING,
) -> float:
    """Choose the diagonal-loading shrinkage parameter by leave-one-out CV.

    Port of NASA emit-sds/emit-ghg/parallel_mf.py::fit_looshrinkage_alpha
    (Apache-2.0; Brodrick, Bue, Thompson, Fahlen, Coleman, JPL). Uses the
    closed-form LOOCV objective of Theiler, "The Incredible Shrinking
    Covariance Estimator", Proc. SPIE, 2012, Eq. 29.

    Given a per-column radiance matrix ``X`` of shape (n_samples, n_bands),
    sweeps α through a log-spaced grid and selects the value minimising

        NLL(α) = ½ (n_b log(2π) + log|G|) + (1/2n) Σ_k [log(q_k) + r_k/q_k]

    where G = n (β S) + α T,  β = (1−α)/(n−1),  S = sample covariance,
    T = diag(S), r_k = X[k] · G⁻¹ · X[k], q_k = 1 − β r_k.

    Args:
        column_radiance: 2-D array (n_samples, n_bands) of GOOD-pixel radiance
            for a single cross-track column. NOT pre-centred; np.cov subtracts
            the per-band mean internally.
        alpha_grid: log-spaced candidate values. Defaults to NASA's grid
            (10**arange(-10, 0+0.05, 0.05) — 201 values).
        stability_scaling: multiplies the data before forming S, preventing
            det(G) underflow on small-magnitude radiance units. Cancels out of
            the LOOCV minimisation in exact arithmetic (matches NASA's 100.0).

    Returns:
        Chosen α in [alpha_grid.min(), alpha_grid.max()]. If every grid value
        gives an undefined NLL (rank-deficient G, q_k ≤ 0), returns 0.0.

    Notes:
        Well-conditioned columns (n_samples >> n_bands, isotropic noise) pick α
        near the grid's lower bound. Ill-conditioned columns (rank-deficient
        S or strong correlated structure) pick α much closer to 1, where C
        becomes nearly diagonal and the C-inverse no longer amplifies tiny
        spectral correlations into bright matched-filter artefacts.
    """
    if alpha_grid is None:
        alpha_grid = _default_alpha_grid()
    grid = np.asarray(alpha_grid, dtype=np.float64)
    x_mat = np.asarray(column_radiance, dtype=np.float64) * float(stability_scaling)
    if x_mat.ndim != 2:
        raise ValueError(
            f"column_radiance must be 2-D (n_samples, n_bands); got {x_mat.shape}"
        )
    n, nchan = x_mat.shape
    if n < 2 or nchan < 1:
        return 0.0

    # rowvar=False so columns of x_mat are variables (bands).
    s_mat = np.cov(x_mat, rowvar=False, ddof=1)
    t_mat = np.diag(np.diag(s_mat))
    nchanlog2pi = nchan * np.log(2.0 * np.pi)
    nll = np.full(grid.size, np.inf, dtype=np.float64)

    for i, alpha in enumerate(grid):
        try:
            beta = (1.0 - alpha) / (n - 1.0)
            g_mat = n * (beta * s_mat) + (alpha * t_mat)
            sign, logdet = np.linalg.slogdet(g_mat)
            if sign <= 0 or not np.isfinite(logdet):
                continue
            g_inv = np.linalg.inv(g_mat)
            r_k = (x_mat @ g_inv * x_mat).sum(axis=1)
            q = 1.0 - beta * r_k
            if not np.all(np.isfinite(q)) or np.any(q <= 0.0):
                continue
            term = np.log(q) + r_k / q
            if not np.all(np.isfinite(term)):
                continue
            nll[i] = 0.5 * (nchanlog2pi + logdet) + (1.0 / (2.0 * n)) * term.sum()
        except (np.linalg.LinAlgError, FloatingPointError):
            continue

    if not np.any(np.isfinite(nll)):
        return 0.0
    return float(grid[int(np.argmin(nll))])


@dataclass(frozen=True)
class MatchedFilterResult:
    """Output of :func:`run_matched_filter`.

    Attributes:
        enhancement_ppm_m: 2-D array (n_lines, n_columns) of methane column
            enhancements in ppm·m. NaN where the pixel was excluded from the MF
            (cloud, water, saturated, masked).
        mu_per_column: 2-D array (n_columns, n_bands_kept) of per-column mean
            radiances used to build μ. Kept so the validation writeup can
            inspect the background model.
        shrinkage_alpha_per_column: 1-D array of length n_columns with the α
            chosen by LOOCV (or the fixed value provided, broadcast). NaN for
            columns skipped due to insufficient good samples.
        band_indices_kept: 1-D indices into the original band axis showing
            which bands were retained by the spectral window mask.
        wavelengths_kept_nm: Wavelengths corresponding to ``band_indices_kept``.
    """

    enhancement_ppm_m: npt.NDArray[np.float64]
    mu_per_column: npt.NDArray[np.float64]
    shrinkage_alpha_per_column: npt.NDArray[np.float64]
    band_indices_kept: npt.NDArray[np.intp]
    wavelengths_kept_nm: npt.NDArray[np.float64]


def run_matched_filter(
    radiance: npt.NDArray[np.float64],
    wavelengths_nm: npt.NDArray[np.float64],
    unit_absorption_spectrum_k: npt.NDArray[np.float64],
    *,
    bad_pixel_mask: npt.NDArray[np.bool_] | None = None,
    spectral_windows_nm: tuple[tuple[float, float], ...] = MF_SPECTRAL_WINDOWS_NM,
    shrinkage_alpha: float | str = MF_SHRINKAGE_ALPHA,
    ppm_scaling_factor: float = MF_PPM_SCALING_FACTOR,
    target_signature_override: npt.NDArray[np.float64] | None = None,
) -> MatchedFilterResult:
    """Run the per-column matched filter on a radiance cube.

    Args:
        radiance: 3-D array of shape ``(n_lines, n_columns, n_bands)``, the raw
            L1B radiance cube in any consistent radiance unit.
        wavelengths_nm: 1-D array of length ``n_bands`` — center wavelengths.
        unit_absorption_spectrum_k: 1-D array of length ``n_bands``, the unit
            absorption spectrum k. It must already carry its intrinsic
            negative sign (methane absorption reduces radiance).
        bad_pixel_mask: 2-D bool array of shape ``(n_lines, n_columns)``. True
            marks pixels excluded from the per-column μ/Σ estimate and also
            set to NaN in the output. None means use all pixels.
        spectral_windows_nm: List of inclusive wavelength windows the MF
            operates on. Defaults to the EMIT operational windows.
        shrinkage_alpha: Diagonal-loading shrinkage parameter. Default is the
            fixed value :data:`MF_SHRINKAGE_ALPHA` = 1e-9 (the validated
            Stage A configuration from EMIT GHG ATBD §4.2.1). A float pins
            α to that value for every column. The string ``"loocv"`` opts
            in to per-column LOOCV fitting via
            :func:`fit_looshrinkage_alpha` — NOT recommended for production
            on EMIT radiance because NASA's uncentered-data variant we
            ported degrades Stage A Pearson without removing blob artefacts
            (see scripts/diagnose_loocv_centering.py and the run report
            stage_a_outputs/.../_pre_loocv/ vs the post-LOOCV diagnostic).
        ppm_scaling_factor: Multiplicative conversion from the raw MF output
            (in units of the MODTRAN Δc baked into the unit absorption
            spectrum) to ppm·m. Defaults to NASA's published value
            (:data:`MF_PPM_SCALING_FACTOR` = 100000.0), valid for the
            EMIT-Data-Resources per-granule target files. **Synthetic tests
            that build k directly in 1/(ppm·m) must pass 1.0** — their k is
            already calibrated so the raw MF output is already in ppm·m.
        target_signature_override: For tests only. If provided, this 2-D array
            ``(n_columns, n_bands_kept)`` is used as the target s INSTEAD of
            building s = k ⊙ μ. The guardrail synthetic-plume tests pass a
            sign-flipped or doubled-μ s through this hook to verify the MF
            output goes wrong as expected.

    Returns:
        :class:`MatchedFilterResult` with the enhancement raster and the
        per-column α actually used.

    Notes:
        Numerical strategy: we solve ``C @ z = s`` once per column using
        :func:`numpy.linalg.solve` rather than forming C⁻¹ explicitly. The
        per-pixel score is then ``(x - μ) @ z / (s @ z)``, computed across the
        column in a single matrix product, then multiplied by
        ``ppm_scaling_factor`` to yield ppm·m.
    """
    rad = np.asarray(radiance, dtype=np.float64)
    if rad.ndim != 3:
        raise ValueError(f"radiance must be 3-D (lines, cols, bands); got shape {rad.shape}")
    n_lines, n_cols, n_bands = rad.shape
    wl = np.asarray(wavelengths_nm, dtype=np.float64)
    k_full = np.asarray(unit_absorption_spectrum_k, dtype=np.float64)
    if wl.shape != (n_bands,) or k_full.shape != (n_bands,):
        raise ValueError(
            f"wavelengths and k must each have shape ({n_bands},); "
            f"got wl={wl.shape}, k={k_full.shape}"
        )

    band_indices_kept = select_band_indices(wl, spectral_windows_nm)
    if band_indices_kept.size < 2:
        raise ValueError("Spectral windows retained fewer than 2 bands; cannot run MF")

    rad_kept = rad[:, :, band_indices_kept]   # (lines, cols, B)
    k_kept = k_full[band_indices_kept]        # (B,)
    wl_kept = wl[band_indices_kept]           # (B,)

    if bad_pixel_mask is None:
        bad = np.zeros((n_lines, n_cols), dtype=bool)
    else:
        bad = np.asarray(bad_pixel_mask, dtype=bool)
        if bad.shape != (n_lines, n_cols):
            raise ValueError(
                f"bad_pixel_mask must have shape (n_lines, n_cols)={n_lines, n_cols}; "
                f"got {bad.shape}"
            )

    # Validate the shrinkage parameter shape: float or the LOOCV opt-in string.
    use_loocv = False
    fixed_alpha: float = MF_SHRINKAGE_ALPHA
    if isinstance(shrinkage_alpha, str):
        if shrinkage_alpha != LOOCV_SENTINEL:
            raise ValueError(
                f"shrinkage_alpha string must be {LOOCV_SENTINEL!r}; got {shrinkage_alpha!r}"
            )
        use_loocv = True
    else:
        fixed_alpha = float(shrinkage_alpha)

    enhancement = np.full((n_lines, n_cols), np.nan, dtype=np.float64)
    n_bands_kept = band_indices_kept.size
    mu_per_column = np.zeros((n_cols, n_bands_kept), dtype=np.float64)
    alpha_per_column = np.full(n_cols, np.nan, dtype=np.float64)
    alpha_grid = _default_alpha_grid() if use_loocv else None

    for c in range(n_cols):
        col = rad_kept[:, c, :]                 # (lines, B)
        good = ~bad[:, c]
        n_good = int(good.sum())
        # Need enough samples to estimate Σ on B bands. Skip columns whose
        # good-pixel count is too small even for the LOOCV objective to be
        # well-defined.
        if n_good < n_bands_kept + 2:
            continue

        good_rows = col[good]                   # (n_good, B)
        mu_c = good_rows.mean(axis=0)           # (B,)
        mu_per_column[c] = mu_c

        # Choose α per column. Default is the fixed ATBD value; LOOCV is an
        # opt-in diagnostic mode and matches NASA's bit-for-bit (which on
        # uncentered EMIT radiance does not help — see constants.py comment).
        if use_loocv:
            alpha_c = fit_looshrinkage_alpha(good_rows, alpha_grid=alpha_grid)
        else:
            alpha_c = fixed_alpha
        alpha_per_column[c] = alpha_c

        # rowvar=False so each column of `deviations` is a variable (band).
        c_empirical = np.cov(good_rows - mu_c, rowvar=False, bias=False)  # (B, B)
        c_shrunk = (1.0 - alpha_c) * c_empirical + alpha_c * np.diag(np.diag(c_empirical))

        if target_signature_override is None:
            s_c = build_target_signature(k_kept, mu_c[None, :])[0]  # (B,)
        else:
            override = np.asarray(target_signature_override, dtype=np.float64)
            if override.shape != (n_cols, n_bands_kept):
                raise ValueError(
                    f"target_signature_override must have shape (n_columns, n_bands_kept)="
                    f"({n_cols}, {n_bands_kept}); got {override.shape}"
                )
            s_c = override[c]

        # Solve C @ z = s once. Then numerator = (x-μ) @ z; denominator = s @ z.
        try:
            z = np.linalg.solve(c_shrunk, s_c)
        except np.linalg.LinAlgError:
            continue
        denom = float(s_c @ z)
        if not np.isfinite(denom) or denom == 0.0:
            continue

        all_rows = col - mu_c                   # (lines, B) — includes bad rows
        alpha_col = (all_rows @ z) / denom      # (lines,) in units of Δc
        enhancement[good, c] = alpha_col[good]

    # Convert from raw MF output (units of MODTRAN's Δc) to ppm·m. NASA's
    # published per-granule target file is calibrated such that this constant
    # equals the Δc perturbation used in MODTRAN (default 100000.0). Tests
    # whose synthetic k is already in 1/(ppm·m) pass ppm_scaling_factor=1.0.
    enhancement *= ppm_scaling_factor

    return MatchedFilterResult(
        enhancement_ppm_m=enhancement,
        mu_per_column=mu_per_column,
        shrinkage_alpha_per_column=alpha_per_column,
        band_indices_kept=band_indices_kept,
        wavelengths_kept_nm=wl_kept,
    )
