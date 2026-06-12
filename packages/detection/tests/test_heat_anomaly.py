"""Tests for the heat-vertical anomaly primitives (offline, synthetic arrays)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest
from aether_detection.heat_anomaly import (
    IMD_ABS_THRESHOLD_K,
    cell_areas_km2,
    coarsen_to_grid,
    day_window_climatology,
    qualifying_mask,
    read_imd_maxtemp_grd,
    run_containing,
    window_dates,
)


class TestImdReader:
    def test_roundtrip_layout_and_missing(self, tmp_path: Path) -> None:
        n_days = 365
        cube = np.full((n_days, 31, 31), 31.5, dtype="<f4")
        cube[10, 19, 8] = 42.7  # a known (day, lat-idx, lon-idx) cell
        cube[0, 0, 0] = 99.9  # missing marker
        path = tmp_path / "maxtemp_2022.grd"
        cube.tofile(path)
        out = read_imd_maxtemp_grd(path, 2022)
        assert out.shape == (365, 31, 31)
        assert out[10, 19, 8] == pytest.approx(42.7)
        assert np.isnan(out[0, 0, 0])

    def test_wrong_size_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "maxtemp_2020.grd"
        np.zeros(10, dtype="<f4").tofile(path)
        with pytest.raises(ValueError, match="expected"):
            read_imd_maxtemp_grd(path, 2020)  # leap year: 366 days expected


class TestClimatologyAndCriterion:
    def test_day_window_mean(self) -> None:
        # 3 years x 5 days x 1 cell; day 2 with half-window 1 averages days 1..3.
        base = np.arange(15, dtype=np.float32).reshape(3, 5, 1, 1)
        clim = day_window_climatology(base, day_index=2, half_window=1)
        expected = np.mean([1, 2, 3, 6, 7, 8, 11, 12, 13])
        assert clim[0, 0] == pytest.approx(expected)

    def test_qualifying_mask_needs_both_conditions(self) -> None:
        clim = np.full((1, 3), 308.15, dtype=np.float32)  # 35 degC normal
        valid = np.ones((1, 3), dtype=bool)
        # cell 0: hot + anomalous; cell 1: hot but NOT anomalous (clim raised);
        # cell 2: anomalous but below 40 degC absolute.
        tmax = np.array([[315.15, 315.15, 312.0]], dtype=np.float32)
        clim2 = clim.copy()
        clim2[0, 1] = 313.0
        mask = qualifying_mask(tmax, clim2, valid)
        assert mask.tolist() == [[True, False, False]]
        assert pytest.approx(313.15) == IMD_ABS_THRESHOLD_K

    def test_qualifying_mask_nan_safe(self) -> None:
        tmax = np.array([[np.nan, 320.0]], dtype=np.float32)
        clim = np.full((1, 2), 300.0, dtype=np.float32)
        mask = qualifying_mask(tmax, clim, np.ones((1, 2), dtype=bool))
        assert mask.tolist() == [[False, True]]


class TestAreasAndRuns:
    def test_cell_area_equator_quarter_degree(self) -> None:
        lats = np.array([0.0, 0.25])
        lons = np.array([0.0, 0.25])
        areas = cell_areas_km2(lats, lons)
        # 0.25 deg ~ 27.8 km at the equator -> ~773 km^2
        assert areas[0, 0] == pytest.approx(773.0, rel=0.01)

    def test_run_containing_anchor(self) -> None:
        days = window_dates(date(2022, 4, 1), date(2022, 4, 14))
        fracs = [0.01, 0.06, 0.07, 0.08, 0.09, 0.1, 0.12, 0.2, 0.1, 0.08, 0.06, 0.02, 0.0, 0.0]
        run = run_containing(days, fracs, anchor=date(2022, 4, 8), threshold=0.05)
        assert run.start == date(2022, 4, 2)
        assert run.end == date(2022, 4, 11)
        assert run.n_days == 10
        assert not run.hit_data_boundary

    def test_run_boundary_flagged(self) -> None:
        days = window_dates(date(2022, 4, 1), date(2022, 4, 5))
        fracs = [0.06, 0.06, 0.07, 0.06, 0.06]
        run = run_containing(days, fracs, anchor=date(2022, 4, 3), threshold=0.05)
        assert run.hit_data_boundary  # touches both computed edges

    def test_non_qualifying_anchor_rejected(self) -> None:
        days = window_dates(date(2022, 4, 1), date(2022, 4, 3))
        with pytest.raises(ValueError, match="does not qualify"):
            run_containing(days, [0.01, 0.01, 0.01], anchor=date(2022, 4, 2), threshold=0.05)


class TestCoarsening:
    def test_cell_mean_onto_1deg(self) -> None:
        fine_lats = np.arange(27.875, 26.825, -0.25)  # descending like ERA5
        fine_lons = np.arange(75.125, 76.175, 0.25)
        fine = np.ones((fine_lats.size, fine_lons.size), dtype=np.float32) * 2.0
        fine[0, 0] = 6.0
        coarse = coarsen_to_grid(
            fine, fine_lats, fine_lons, np.array([27.5]), np.array([75.5])
        )
        sel_lat = (fine_lats >= 27.0) & (fine_lats < 28.0)
        sel_lon = (fine_lons >= 75.0) & (fine_lons < 76.0)
        assert coarse[0, 0] == pytest.approx(float(fine[np.ix_(sel_lat, sel_lon)].mean()))

    def test_all_nan_block_stays_nan(self) -> None:
        fine = np.full((2, 2), np.nan, dtype=np.float32)
        out = coarsen_to_grid(
            fine,
            np.array([27.6, 27.4]),
            np.array([75.4, 75.6]),
            np.array([27.5]),
            np.array([75.5]),
        )
        assert np.isnan(out[0, 0])
