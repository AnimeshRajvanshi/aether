"""Source-connected plume mask construction (Varon 2018 §5.1).

Verbatim implementation of the mask procedure described in:

  Varon, D. J., et al. (2018). Quantifying methane point sources from fine-scale
  satellite observations of atmospheric methane plumes. AMT 11, 5673-5686
  (doi:10.5194/amt-11-5673-2018), §5.1, Fig. 3.

Algorithm (per Varon):

1. **Background distribution**: mean μ_bg, variance σ_bg² from a sample of
   pixels known (or assumed) to be free of plume signal. Varon uses an
   "upwind sample"; we accept any user-supplied 2-D boolean mask of
   background pixels and use the empirical (mean, variance, count) over it.

2. **Per-pixel Student's t-test**: for each pixel, sample its 5×5
   neighbourhood. Compute Welch's two-sample t-statistic between that
   sample and the background distribution. Flag the pixel as a plume
   candidate if the sample distribution is significantly *larger* than
   background at p < 0.05 (one-sided, plume enhancement is positive).

3. **Smooth the boolean candidate mask**: a 3×3 median filter (removes
   isolated speckle), then a Gaussian filter (σ = 2 by default, Varon
   suggests 2-5 for higher-noise data), then threshold > 0.5 to produce a
   final boolean mask.

4. **Connected-component labelling**: assign each contiguous region of
   plume pixels a distinct integer label via scipy.ndimage.label with
   8-connectivity. Background pixels get label 0. The "plume" for IME
   integration is one of these labelled components — the one anchored
   at the source (see :func:`component_label_at_point`).

The point of step 4 is exactly the property the user is testing in this
sprint: spatially disjoint enhancement features become *distinct
connected components* and are therefore separated automatically, without
any hand-drawn exclusion box.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import scipy.ndimage as ndi
import scipy.stats

# Varon 2018 §5.1 — fixed algorithmic constants. None of these are tunable
# knobs we adjust during validation; they are the paper's prescription.
SEGMENTATION_NEIGHBORHOOD_SIZE: int = 5
SEGMENTATION_T_TEST_PVALUE: float = 0.05
SEGMENTATION_MEDIAN_FILTER_SIZE: int = 3
SEGMENTATION_GAUSSIAN_SIGMA: float = 2.0
SEGMENTATION_SMOOTHED_THRESHOLD: float = 0.5
# 8-connectivity for connected-component labelling — diagonal neighbours
# count as part of the same plume. Matches Varon's implicit choice and
# scipy.ndimage's `structure=np.ones((3,3))` semantics.
SEGMENTATION_CONNECTIVITY_STRUCTURE: npt.NDArray[np.intp] = np.ones((3, 3), dtype=np.intp)


@dataclass(frozen=True)
class SegmentationResult:
    """Output of :func:`segment_plume_varon`.

    Attributes:
        plume_mask: 2-D boolean array; True for pixels assigned to a plume
            connected component (any label > 0).
        labels: 2-D integer array of connected-component labels. 0 means
            background. 1, 2, ... are distinct plume components.
        n_components: Number of distinct plume components found.
        component_pixel_counts: 1-D array of length n_components+1 giving
            the pixel count for each label (index 0 = background count).
        background_mean: μ_bg used in the t-test.
        background_variance: σ_bg² used in the t-test.
        background_n: number of pixels in the background sample.
    """

    plume_mask: npt.NDArray[np.bool_]
    labels: npt.NDArray[np.intp]
    n_components: int
    component_pixel_counts: npt.NDArray[np.intp]
    background_mean: float
    background_variance: float
    background_n: int


def segment_plume_varon(
    enhancement: npt.NDArray[np.float64],
    background_mask: npt.NDArray[np.bool_],
    *,
    neighborhood_size: int = SEGMENTATION_NEIGHBORHOOD_SIZE,
    p_value: float = SEGMENTATION_T_TEST_PVALUE,
    median_filter_size: int = SEGMENTATION_MEDIAN_FILTER_SIZE,
    gaussian_sigma: float = SEGMENTATION_GAUSSIAN_SIGMA,
    smoothed_threshold: float = SEGMENTATION_SMOOTHED_THRESHOLD,
) -> SegmentationResult:
    """Build a source-connected plume mask via Varon 2018 §5.1.

    Args:
        enhancement: 2-D array of methane column enhancements (ppm·m).
            NaN pixels (e.g. outside the swath) are treated as non-plume.
        background_mask: 2-D boolean array, same shape as ``enhancement``,
            identifying pixels to draw the background distribution from.
            Must include only off-plume pixels. Pixels with NaN values are
            silently excluded from the sample.
        neighborhood_size: kernel size for the per-pixel sampling window
            (Varon: 5). Must be odd ≥ 3.
        p_value: one-sided significance threshold (Varon: 0.05).
        median_filter_size: kernel for the post-t-test median smooth
            (Varon: 3).
        gaussian_sigma: Gaussian smoothing σ in pixels (Varon: 2-5).
        smoothed_threshold: cutoff on the smoothed [0,1] mask
            (Varon: > 0.5 after threshold).

    Returns:
        :class:`SegmentationResult` with the boolean plume mask and labeled
        connected components.
    """
    enh = np.asarray(enhancement, dtype=np.float64)
    if enh.ndim != 2:
        raise ValueError(f"enhancement must be 2-D; got shape {enh.shape}")
    bg = np.asarray(background_mask, dtype=bool)
    if bg.shape != enh.shape:
        raise ValueError(
            f"background_mask shape {bg.shape} != enhancement shape {enh.shape}"
        )
    if neighborhood_size % 2 == 0 or neighborhood_size < 3:
        raise ValueError(f"neighborhood_size must be odd ≥ 3; got {neighborhood_size}")

    # --- 1. Background distribution ----------------------------------------
    bg_values = enh[bg & np.isfinite(enh)]
    bg_n = int(bg_values.size)
    if bg_n < neighborhood_size * neighborhood_size:
        raise ValueError(
            f"Background sample too small: n={bg_n}; need at least "
            f"{neighborhood_size * neighborhood_size} pixels."
        )
    mu_bg = float(bg_values.mean())
    var_bg = float(bg_values.var(ddof=1))

    # --- 2. Per-pixel Welch's t-test on the 5×5 neighbourhood --------------
    # We compute per-pixel local mean and variance over the neighbourhood by
    # uniform-filtering the enhancement and its square. NaN-safe by treating
    # NaN as a hard exclusion: replace NaN with mu_bg during the convolution
    # and track the per-pixel valid-sample count to avoid biasing means and
    # variances on swath boundaries.
    finite = np.isfinite(enh)
    enh_filled = np.where(finite, enh, 0.0)
    valid_kernel = ndi.uniform_filter(finite.astype(np.float64), size=neighborhood_size)
    # Per-pixel sample count over the local kernel.
    n_local = valid_kernel * (neighborhood_size * neighborhood_size)
    # Local sum / sum of squares.
    sum_local = ndi.uniform_filter(enh_filled, size=neighborhood_size) * (
        neighborhood_size * neighborhood_size
    )
    sqsum_local = ndi.uniform_filter(enh_filled ** 2, size=neighborhood_size) * (
        neighborhood_size * neighborhood_size
    )
    # Mean and unbiased sample variance over the n_local samples; guard
    # against zero-or-one-sample cells where variance is undefined.
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_local = sum_local / n_local
        var_local = (sqsum_local - n_local * mean_local ** 2) / np.maximum(n_local - 1.0, 1.0)
    var_local = np.maximum(var_local, 0.0)

    # Welch's t and Welch-Satterthwaite degrees of freedom, fully vectorised.
    se_sq_local = np.where(n_local > 0, var_local / np.maximum(n_local, 1.0), np.inf)
    se_sq_bg = var_bg / bg_n
    se = np.sqrt(se_sq_local + se_sq_bg)
    with np.errstate(invalid="ignore", divide="ignore"):
        t_stat = (mean_local - mu_bg) / se
        # Welch-Satterthwaite df
        num = (se_sq_local + se_sq_bg) ** 2
        denom = (
            se_sq_local ** 2 / np.maximum(n_local - 1.0, 1.0)
            + se_sq_bg ** 2 / max(bg_n - 1, 1)
        )
        df = num / np.where(denom > 0, denom, np.inf)

    # One-sided upper-tail p-value: P(T > t_stat | H0).
    p_local = scipy.stats.t.sf(t_stat, df)
    # A plume candidate is a pixel whose 5×5 neighbourhood mean is
    # significantly LARGER than background at the chosen p threshold, AND
    # the kernel was at least half full (avoids edge artefacts).
    candidate = (p_local < p_value) & (n_local >= (neighborhood_size * neighborhood_size) / 2)
    # Pixels outside the swath are never plume.
    candidate &= finite

    # --- 3. Smooth the candidate mask --------------------------------------
    smoothed = ndi.median_filter(candidate.astype(np.float64), size=median_filter_size)
    smoothed = ndi.gaussian_filter(smoothed, sigma=gaussian_sigma)
    plume_mask = smoothed > smoothed_threshold

    # --- 4. Connected-component labelling ---------------------------------
    labels, n_components = ndi.label(plume_mask, structure=SEGMENTATION_CONNECTIVITY_STRUCTURE)
    if n_components > 0:
        # Pixel count per label including 0 (background).
        counts = np.bincount(labels.ravel(), minlength=n_components + 1).astype(np.intp)
    else:
        counts = np.array([int(labels.size)], dtype=np.intp)

    return SegmentationResult(
        plume_mask=plume_mask,
        labels=labels,
        n_components=int(n_components),
        component_pixel_counts=counts,
        background_mean=mu_bg,
        background_variance=var_bg,
        background_n=bg_n,
    )


def component_label_at_point(
    labels: npt.NDArray[np.intp],
    lon_centers: npt.NDArray[np.float64],
    lat_centers: npt.NDArray[np.float64],
    target_lon: float,
    target_lat: float,
) -> int:
    """Return the connected-component label at a given (lon, lat) point.

    Args:
        labels: 2-D integer label array from :func:`segment_plume_varon`.
        lon_centers: 1-D array of pixel-centre longitudes along the x axis.
        lat_centers: 1-D array of pixel-centre latitudes along the y axis.
        target_lon, target_lat: query coordinates.

    Returns:
        The integer label at that pixel (0 for background). Raises if the
        point falls outside the raster.
    """
    lon_idx = int(np.argmin(np.abs(lon_centers - target_lon)))
    lat_idx = int(np.argmin(np.abs(lat_centers - target_lat)))
    if (
        not (0 <= lat_idx < labels.shape[0])
        or not (0 <= lon_idx < labels.shape[1])
    ):
        raise ValueError(
            f"Point ({target_lon}, {target_lat}) outside raster extent."
        )
    return int(labels[lat_idx, lon_idx])


def largest_component_in_region(
    labels: npt.NDArray[np.intp],
    lon_centers: npt.NDArray[np.float64],
    lat_centers: npt.NDArray[np.float64],
    min_lon: float,
    max_lon: float,
    min_lat: float,
    max_lat: float,
) -> int:
    """Return the label of the largest connected component intersecting a bbox.

    Returns 0 (background) if no plume component intersects the bbox.
    """
    lon_mask = (lon_centers >= min_lon) & (lon_centers <= max_lon)
    lat_mask = (lat_centers >= min_lat) & (lat_centers <= max_lat)
    sub = labels[np.ix_(lat_mask, lon_mask)]
    if sub.size == 0:
        return 0
    plume_labels = sub[sub > 0]
    if plume_labels.size == 0:
        return 0
    unique, counts = np.unique(plume_labels, return_counts=True)
    return int(unique[int(np.argmax(counts))])
