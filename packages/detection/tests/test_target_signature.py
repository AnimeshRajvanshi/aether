"""Unit tests for aether_detection.target_signature.

These keep the k/μ/s naming and composition explicit. The deeper guardrail
tests live in test_matched_filter.py.
"""

from __future__ import annotations

import numpy as np
import pytest
from aether_detection.target_signature import (
    build_target_signature,
    load_unit_absorption_spectrum,
    select_band_indices,
)


def test_build_target_signature_correct_composition() -> None:
    """s = k ⊙ μ, broadcasting a 1-D k across columns."""
    n_cols, n_bands = 3, 5
    k = np.array([-1.0, -2.0, -3.0, -4.0, -5.0])
    mu = np.arange(n_cols * n_bands, dtype=float).reshape(n_cols, n_bands) + 1.0
    s = build_target_signature(k, mu)
    assert s.shape == (n_cols, n_bands)
    expected = k[None, :] * mu
    np.testing.assert_allclose(s, expected)


def test_build_target_signature_rejects_shape_mismatch() -> None:
    k = np.zeros(4)
    mu = np.zeros((2, 5))
    with pytest.raises(ValueError, match="same band axis length"):
        build_target_signature(k, mu)


def test_build_target_signature_rejects_1d_mu() -> None:
    k = np.zeros(5)
    mu = np.zeros(5)  # 1-D mu — not allowed
    with pytest.raises(ValueError, match="μ must be 2-D"):
        build_target_signature(k, mu)


def test_select_band_indices_methane_window() -> None:
    """Only bands inside the windows survive."""
    wl = np.array([400.0, 500.0, 1000.0, 1340.0, 1500.0, 1800.0, 2000.0, 2450.0, 2500.0])
    windows = ((500.0, 1340.0), (1500.0, 1790.0), (1950.0, 2450.0))
    indices = select_band_indices(wl, windows)
    kept = wl[indices].tolist()
    # 400 (out), 1800 (out), 2500 (out) excluded. 500 and 1340 included
    # at the inclusive endpoints.
    assert kept == [500.0, 1000.0, 1340.0, 1500.0, 2000.0, 2450.0]


def test_load_unit_absorption_spectrum(tmp_path) -> None:
    """Round-trip through the plaintext NASA-tutorial format.

    Format is space-separated columns: index, wavelength_nm, value (1/(ppm·m)).
    Sign is preserved verbatim.
    """
    path = tmp_path / "ch4_target.txt"
    rows = np.array(
        [
            [0, 500.0, 0.0],
            [1, 1000.0, -1.5e-5],
            [2, 2300.0, -1.0e-4],
            [3, 2450.0, -3.2e-5],
        ]
    )
    np.savetxt(path, rows)
    wl, k = load_unit_absorption_spectrum(path)
    np.testing.assert_allclose(wl, [500.0, 1000.0, 2300.0, 2450.0])
    np.testing.assert_allclose(k, [0.0, -1.5e-5, -1.0e-4, -3.2e-5])
    # k must retain its sign — absorption coefficients are negative-valued
    # in this convention.
    assert np.all(k <= 0.0)


def test_load_unit_absorption_spectrum_rejects_short_format(tmp_path) -> None:
    path = tmp_path / "bad.txt"
    np.savetxt(path, np.array([[1.0, 2.0]]))  # only 2 cols
    with pytest.raises(ValueError, match="at least 3 columns"):
        load_unit_absorption_spectrum(path)
