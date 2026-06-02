"""Synthetic-plume tests for the per-column matched filter.

The headline test is :func:`test_recovers_injected_plume_correctly`. It builds
a synthetic radiance cube with a known methane column enhancement injected via
the Beer-Lambert linearization, runs our MF, and checks the recovered value
matches the truth.

The headline test is paired with two GUARDRAIL tests that protect against the
two most likely silent bugs in this kind of code: a flipped sign on the target
signature, and an extra factor of μ in the target composition (s = k⊙μ⊙μ
instead of s = k⊙μ). Both guardrail tests must fail loudly — they assert that
when the *wrong* target is passed in, the MF output is correspondingly wrong.
If a future refactor accidentally introduces either bug, these tests will catch
it because they would no longer fail.

Theory used here
----------------
Beer-Lambert linearization (Thompson 2015 Eq. 9-12):

    L(λ) = μ(λ) * exp(-σ(λ) * c)
         ≈ μ(λ) * (1 - σ(λ) * c)        for small c
         = μ(λ) + (μ(λ) * (-σ(λ))) * c

Define k(λ) = -σ(λ) (the signed Jacobian (1/L)·∂L/∂c). Then:

    L(λ) ≈ μ(λ) + (k(λ) * μ(λ)) * c
         ≈ μ(λ) + s(λ) * α            with s = k⊙μ, α = c

so injecting α ppm·m of CH4 means adding s*α to the background radiance.
"""

from __future__ import annotations

import numpy as np
import pytest
from aether_detection import constants
from aether_detection.matched_filter import fit_looshrinkage_alpha, run_matched_filter
from aether_detection.target_signature import (
    build_target_signature,
    select_band_indices,
)

# --------------------------------------------------------------------------- #
# Synthetic scene builder
# --------------------------------------------------------------------------- #


def _gaussian_methane_k(wavelengths_nm: np.ndarray) -> np.ndarray:
    """Synthetic unit absorption spectrum k(λ).

    Single Gaussian dip centered on the 2300 nm CH4 absorption complex. This is
    NOT a physically accurate methane spectrum — it is the simplest function
    that produces a recognizable absorption feature within the EMIT MF window,
    which is all the linearity test needs. k carries its intrinsic negative
    sign (radiance falls as methane rises).

    Returns k in units of 1/(ppm·m). The peak magnitude (1e-4) is chosen so
    that a 1000 ppm·m injection produces a ~10% radiance dip — well within the
    Beer-Lambert linearization regime.
    """
    peak_nm = 2300.0
    sigma_nm = 60.0
    k_peak = -1.0e-4  # 1/(ppm·m), negative because absorption reduces radiance
    return k_peak * np.exp(-0.5 * ((wavelengths_nm - peak_nm) / sigma_nm) ** 2)


def _synthetic_scene(
    *,
    alpha_true_ppm_m: float = 1000.0,
    n_lines: int = 1280,
    n_cols: int = 32,
    plume_line_slice: slice = slice(500, 508),
    plume_col_slice: slice = slice(14, 18),
    noise_std_frac: float = 0.005,
    seed: int = 7,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    """Build a synthetic radiance cube with a known plume.

    Returns:
        ``(radiance, wavelengths_nm, k, plume_mask, alpha_true_ppm_m)``.
    """
    rng = np.random.default_rng(seed)

    # Cover the EMIT range coarsely so MF_SPECTRAL_WINDOWS_NM retains bands.
    wavelengths_nm = np.linspace(500.0, 2450.0, 60)
    k = _gaussian_methane_k(wavelengths_nm)

    # Smooth background radiance shape (arbitrary units; only relative matters).
    base = 50.0 + 20.0 * np.exp(-0.5 * ((wavelengths_nm - 1500.0) / 600.0) ** 2)

    # Per-column gain modulates μ across cross-track so per-column statistics
    # are non-trivial — mirrors the push-broom cross-track gain variations
    # that motivate the per-column MF in the first place.
    gain_per_col = 1.0 + 0.05 * np.sin(np.linspace(0.0, 2.0 * np.pi, n_cols))

    # Background radiance: (lines, cols, bands)
    radiance = (
        gain_per_col[None, :, None]
        * base[None, None, :]
        * np.ones((n_lines, n_cols, wavelengths_nm.size))
    )

    # Inject Beer-Lambert plume. Linearization is fine for small c; we also use
    # the exact exp form to stay safe at the chosen peak depth.
    plume_mask = np.zeros((n_lines, n_cols), dtype=bool)
    plume_mask[plume_line_slice, plume_col_slice] = True
    # σ(λ) = -k(λ) (k is the signed Jacobian; absorption coefficient is positive).
    sigma = -k
    transmission = np.exp(-sigma * alpha_true_ppm_m)  # (n_bands,)
    radiance[plume_mask] = radiance[plume_mask] * transmission[None, :]

    # Add Gaussian radiance noise (multiplicative percentage of mean radiance).
    noise = rng.normal(0.0, noise_std_frac, size=radiance.shape) * radiance.mean()
    radiance = radiance + noise

    return radiance, wavelengths_nm, k, plume_mask, alpha_true_ppm_m


# --------------------------------------------------------------------------- #
# Headline test — MF recovers the injected plume
# --------------------------------------------------------------------------- #


def test_recovers_injected_plume_correctly() -> None:
    """End-to-end: inject α=1000 ppm·m, MF recovers it within tolerance.

    Scene size matches a real EMIT acquisition (1280 downtrack lines) so the
    plume occupies <1% of any column and contaminates the per-column μ/Σ
    estimate only slightly. Tolerance is 15% relative — a known small negative
    bias remains from the plume's contribution to the background statistics,
    which the EMIT operational pipeline mitigates via manual plume exclusion
    (ATBD §4.2.1). Tightening below ~10% would require implementing that
    second pass and is out of scope for the synthetic guardrail test.
    """
    radiance, wl, k, plume_mask, alpha_true = _synthetic_scene()

    # Synthetic k is calibrated directly in 1/(ppm·m), so the raw MF output is
    # already in ppm·m; bypass the production ppm_scaling_factor=100000.0 default
    # (which is specific to NASA's per-granule MODTRAN target).
    result = run_matched_filter(
        radiance=radiance,
        wavelengths_nm=wl,
        unit_absorption_spectrum_k=k,
        ppm_scaling_factor=1.0,
    )

    plume_values = result.enhancement_ppm_m[plume_mask]
    bg_mask = ~plume_mask
    bg_values = result.enhancement_ppm_m[bg_mask]

    # Background should be near zero, plume should be near α_true, and the
    # signal-to-background ratio should be large.
    assert np.nanmedian(bg_values) == pytest.approx(0.0, abs=0.10 * alpha_true)
    assert np.nanmedian(plume_values) == pytest.approx(alpha_true, rel=0.15)

    # Strong positive separation: plume median dominates background spread.
    assert np.nanmedian(plume_values) > np.nanmedian(bg_values) + 3.0 * np.nanstd(bg_values)


# --------------------------------------------------------------------------- #
# Guardrail #1: flipped sign in the target signature must break the MF
# --------------------------------------------------------------------------- #


def test_guardrail_flipped_sign_inverts_recovered_enhancement() -> None:
    """If s is built with the wrong sign (s = -k⊙μ instead of s = k⊙μ), the
    matched filter must return inverted recovered values: a positive injected
    plume must come back as a strongly NEGATIVE recovered enhancement.

    This test exists so that any future refactor that silently negates k or s
    will fail loudly. If this test ever stops failing as expected when given
    a sign-flipped target, the production sign convention has drifted.
    """
    radiance, wl, k, plume_mask, alpha_true = _synthetic_scene()

    # Build per-column μ ourselves to construct the wrong target.
    band_indices = select_band_indices(wl, constants.MF_SPECTRAL_WINDOWS_NM)
    n_cols = radiance.shape[1]
    n_bands_kept = band_indices.size
    mu = np.zeros((n_cols, n_bands_kept))
    for c in range(n_cols):
        mu[c] = radiance[:, c, band_indices].mean(axis=0)

    # WRONG: build s with k flipped (s_bad = (-k) ⊙ μ).
    s_correct = build_target_signature(k[band_indices], mu)
    s_flipped = -s_correct

    result = run_matched_filter(
        radiance=radiance,
        wavelengths_nm=wl,
        unit_absorption_spectrum_k=k,
        target_signature_override=s_flipped,
        ppm_scaling_factor=1.0,
    )

    plume_median = float(np.nanmedian(result.enhancement_ppm_m[plume_mask]))
    # A correctly oriented MF returns ~+alpha_true; flipped sign must return
    # roughly -alpha_true. We require the median to be strongly negative.
    assert plume_median < -0.5 * alpha_true, (
        f"Sign-flipped target should invert the recovered enhancement, "
        f"but plume median was {plume_median:.1f} ppm·m (expected ~ -{alpha_true:.0f})"
    )


# --------------------------------------------------------------------------- #
# Guardrail #2: doubled-μ in the target composition must break the MF
# --------------------------------------------------------------------------- #


def test_guardrail_doubled_mu_breaks_quantification() -> None:
    """If s is built as s = k⊙μ⊙μ instead of s = k⊙μ, the matched filter
    must NOT recover α_true. The recovered value should be wrong by orders of
    magnitude because the target's units no longer correspond to ppm·m.

    Specifically, the denominator s^T C⁻¹ s scales as μ², while the numerator
    (x-μ)^T C⁻¹ s scales as μ; the ratio carries an unintended 1/μ scaling
    and α comes out roughly 1/μ̄ times too small.
    """
    radiance, wl, k, plume_mask, alpha_true = _synthetic_scene()

    band_indices = select_band_indices(wl, constants.MF_SPECTRAL_WINDOWS_NM)
    n_cols = radiance.shape[1]
    n_bands_kept = band_indices.size
    mu = np.zeros((n_cols, n_bands_kept))
    for c in range(n_cols):
        mu[c] = radiance[:, c, band_indices].mean(axis=0)

    # WRONG: doubled-μ composition.
    s_doubled = build_target_signature(k[band_indices], mu) * mu  # k⊙μ⊙μ

    result = run_matched_filter(
        radiance=radiance,
        wavelengths_nm=wl,
        unit_absorption_spectrum_k=k,
        target_signature_override=s_doubled,
        ppm_scaling_factor=1.0,
    )

    plume_median = float(np.nanmedian(result.enhancement_ppm_m[plume_mask]))
    # The recovered value must fall far outside the headline test's "correct"
    # envelope. The doubled-μ composition adds an extra radiance factor in s,
    # which scales α by ~1/μ̄ — so the recovered value comes out ~two orders
    # of magnitude TOO SMALL, not too large. We assert the recovered value is
    # less than half of the true α (well outside the 15% headline tolerance).
    assert abs(plume_median - alpha_true) > 0.5 * alpha_true, (
        f"Doubled-μ target should NOT recover α_true correctly, "
        f"but plume median was {plume_median:.1f} ppm·m vs truth {alpha_true:.0f}"
    )
    assert plume_median < 0.5 * alpha_true, (
        f"Expected doubled-μ to under-recover by orders of magnitude; "
        f"got plume median {plume_median:.1f} ppm·m vs truth {alpha_true:.0f}"
    )


# --------------------------------------------------------------------------- #
# Behavioural tests for the implementation
# --------------------------------------------------------------------------- #


def test_spectral_window_filtering_drops_out_of_window_bands() -> None:
    """The MF should only use bands inside MF_SPECTRAL_WINDOWS_NM."""
    radiance, wl, k, _, _ = _synthetic_scene()
    result = run_matched_filter(
        radiance=radiance,
        wavelengths_nm=wl,
        unit_absorption_spectrum_k=k,
    )
    kept_wl = result.wavelengths_kept_nm
    for w in kept_wl:
        assert any(lo <= w <= hi for lo, hi in constants.MF_SPECTRAL_WINDOWS_NM), (
            f"Band at {w} nm was kept but is outside MF_SPECTRAL_WINDOWS_NM"
        )


def test_bad_pixel_mask_propagates_to_nan() -> None:
    """Pixels in the bad mask must come back as NaN in the enhancement raster."""
    radiance, wl, k, _, _ = _synthetic_scene()
    bad = np.zeros(radiance.shape[:2], dtype=bool)
    bad[0:5, :] = True  # exclude top 5 lines
    result = run_matched_filter(
        radiance=radiance,
        wavelengths_nm=wl,
        unit_absorption_spectrum_k=k,
        bad_pixel_mask=bad,
    )
    assert np.all(np.isnan(result.enhancement_ppm_m[0:5, :]))
    # Good pixels are not all-NaN.
    assert not np.all(np.isnan(result.enhancement_ppm_m[5:, :]))


# --------------------------------------------------------------------------- #
# LOOCV shrinkage — mechanism test
# --------------------------------------------------------------------------- #


def test_looshrinkage_picks_larger_alpha_for_ill_conditioned_column() -> None:
    """The LOOCV-fit shrinkage parameter must be larger on an ill-conditioned
    per-column data set than on a well-conditioned one.

    Mechanism: a well-conditioned column has many independent samples per
    band, an isotropic-noise covariance, and small α is safe — the inverse
    of the empirical Σ is well-defined and the matched filter benefits from
    sharper whitening. An ill-conditioned column (few samples relative to
    bands, or strong rank-deficient structure) needs α near 1 so that
    C ≈ diag(C) — otherwise the C-inverse amplifies tiny spectral
    correlations into the bright-blob artefacts seen on real EMIT scenes.

    The test is on MECHANISM, not magnitude. We assert α_ill > α_well by a
    comfortable margin but do not check specific numerical values, because
    LOOCV's chosen value depends on the synthetic distribution and could
    drift with NumPy / SciPy version changes. What must never drift is the
    ordering: ill > well.

    Note on zero-mean inputs: the LOOCV objective r_k = X[k]ᵀ G⁻¹ X[k] uses
    UN-CENTERED X by design in NASA's port (data are not de-meaned before
    fit_looshrinkage_alpha is called). With non-zero-mean inputs the
    objective picks up a mean-Mahalanobis term that biases toward larger α
    for every column. This is the operational behaviour we replicate
    verbatim — but for testing the mechanism cleanly, we feed zero-mean
    synthetic data so that the LOOCV objective behaves as Theiler 2012
    intended (centred Mahalanobis), and the well/ill distinction is what
    drives α selection.
    """
    # Build a single fixed covariance, then draw "well" and "ill" sample
    # sets from the SAME distribution — only the sample count differs.
    # That isolates the effect we want to test: with few samples, the
    # empirical covariance is a poor estimate of the true one, and LOOCV
    # responds by selecting a much larger α (more shrinkage toward the
    # diagonal). With many samples, the empirical covariance is reliable
    # and LOOCV is happy with a much smaller α.
    n_bands = 8
    eigvals = np.linspace(0.5, 5.0, n_bands)
    seed_rng = np.random.default_rng(2026)
    q_mat, _ = np.linalg.qr(seed_rng.standard_normal((n_bands, n_bands)))
    chol = (q_mat * np.sqrt(eigvals)) @ q_mat.T

    well_rng = np.random.default_rng(1)
    well = (chol @ well_rng.standard_normal((n_bands, 1000))).T

    ill_rng = np.random.default_rng(1)
    ill = (chol @ ill_rng.standard_normal((n_bands, 12))).T

    alpha_well = fit_looshrinkage_alpha(well)
    alpha_ill = fit_looshrinkage_alpha(ill)

    assert alpha_well >= 0.0
    assert alpha_ill > alpha_well, (
        f"LOOCV must pick larger α on the under-sampled column. "
        f"Got alpha_well={alpha_well:.3e}  alpha_ill={alpha_ill:.3e}"
    )
    # The ill case should be MUCH larger — at least 30× the well case —
    # so the ordering can't be claimed from grid-step quantisation alone.
    assert alpha_ill > 30.0 * alpha_well, (
        f"Expected α_ill >> α_well (at least 30×) to demonstrate the "
        f"regularisation kicking in; got alpha_well={alpha_well:.3e}, "
        f"alpha_ill={alpha_ill:.3e}, ratio={alpha_ill / alpha_well:.1f}"
    )


def test_run_matched_filter_loocv_optin_records_per_column_alpha() -> None:
    """The ``shrinkage_alpha='loocv'`` opt-in must actually call LOOCV and
    populate per-column α with non-default values. The default code path
    (fixed α=1e-9) records 1e-9 in every column; LOOCV records something
    else. Anything else means the opt-in is silently broken.
    """
    radiance, wl, k, _, _ = _synthetic_scene()
    fixed = run_matched_filter(
        radiance=radiance,
        wavelengths_nm=wl,
        unit_absorption_spectrum_k=k,
        ppm_scaling_factor=1.0,
    )
    loocv = run_matched_filter(
        radiance=radiance,
        wavelengths_nm=wl,
        unit_absorption_spectrum_k=k,
        ppm_scaling_factor=1.0,
        shrinkage_alpha="loocv",
    )
    # Default: every column logs fixed α.
    finite_fixed = fixed.shrinkage_alpha_per_column[np.isfinite(fixed.shrinkage_alpha_per_column)]
    np.testing.assert_allclose(finite_fixed, constants.MF_SHRINKAGE_ALPHA, rtol=1e-12, atol=0)
    # LOOCV: at least one column picks an α materially different from 1e-9.
    finite_loocv = loocv.shrinkage_alpha_per_column[np.isfinite(loocv.shrinkage_alpha_per_column)]
    assert np.any(finite_loocv > 1e-6), (
        f"LOOCV opt-in did not change any α away from the fixed default; "
        f"max α logged was {finite_loocv.max():.3e}"
    )


def test_run_matched_filter_rejects_unknown_shrinkage_alpha_string() -> None:
    """An unknown string opt-in must raise — silent fallback to a default
    would hide bugs where the caller typo'd 'loocv'.
    """
    radiance, wl, k, _, _ = _synthetic_scene()
    with pytest.raises(ValueError, match="shrinkage_alpha string must be"):
        run_matched_filter(
            radiance=radiance,
            wavelengths_nm=wl,
            unit_absorption_spectrum_k=k,
            shrinkage_alpha="LooCv",  # wrong casing — not a typo, an enforced contract
        )


def test_looshrinkage_handles_degenerate_input_without_crashing() -> None:
    """Pathological inputs (n_samples < 2, all-zero data) must not raise."""
    # n_samples = 0 → returns 0.0 without exception.
    assert fit_looshrinkage_alpha(np.zeros((0, 5))) == 0.0
    # n_samples = 1 → covariance is undefined; returns 0.0.
    assert fit_looshrinkage_alpha(np.zeros((1, 5))) == 0.0
    # Constant column: covariance is singular; should still complete and
    # return some grid value (likely the largest α, where C = diag(S) = 0
    # is still picked but the function does not throw).
    out = fit_looshrinkage_alpha(np.full((30, 5), 7.0))
    assert isinstance(out, float)


def test_input_shape_validation() -> None:
    """Bogus shapes are rejected with a clear error."""
    wl = np.linspace(500.0, 2450.0, 60)
    k = np.zeros(60)
    with pytest.raises(ValueError, match="radiance must be 3-D"):
        run_matched_filter(
            radiance=np.zeros((10, 60)),  # wrong: 2-D
            wavelengths_nm=wl,
            unit_absorption_spectrum_k=k,
        )
    with pytest.raises(ValueError, match="wavelengths and k must"):
        run_matched_filter(
            radiance=np.zeros((10, 5, 60)),
            wavelengths_nm=wl[:50],  # wrong: 50 vs 60
            unit_absorption_spectrum_k=k,
        )
