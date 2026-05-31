"""Unit tests for reproduce command."""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
import xarray as xr

from aether_cli import reproduce


class TestReproduce:
    """Test suite for the reproduce module."""

    def test_render_plume_png(self, tmp_path: Path) -> None:
        """Test PNG rendering from methane enhancement data."""
        # Create mock methane enhancement data
        ch4_enh = xr.DataArray(
            np.random.rand(100, 100) * 1000,  # Random enhancement values
            dims=["y", "x"],
            coords={
                "x": np.linspace(-104.2, -104.1, 100),
                "y": np.linspace(32.2, 32.3, 100),
            },
            attrs={"units": "ppm m"},
        )

        output_path = tmp_path / "test_plume.png"

        # Render
        reproduce.render_plume_png(ch4_enh, output_path, event_id="test_event")

        # Verify PNG was created
        assert output_path.exists()
        assert output_path.suffix == ".png"

        # Verify it's a valid PNG (basic check: file size > 0)
        assert output_path.stat().st_size > 0

    def test_render_plume_png_with_nans(self, tmp_path: Path) -> None:
        """Test PNG rendering handles NaN values correctly."""
        # Create data with NaNs
        data = np.random.rand(50, 50) * 1000
        data[:10, :10] = np.nan  # Add NaN region

        ch4_enh = xr.DataArray(
            data,
            dims=["y", "x"],
            coords={
                "x": np.linspace(-104.2, -104.1, 50),
                "y": np.linspace(32.2, 32.3, 50),
            },
            attrs={"units": "ppm m"},
        )

        output_path = tmp_path / "test_plume_nans.png"

        # Should not raise
        reproduce.render_plume_png(ch4_enh, output_path, event_id="test_event")

        assert output_path.exists()

    def test_reproduce_event_no_granules(self) -> None:
        """Test reproduce when no EMIT granules are found."""
        with patch("aether_cli.reproduce.load_event") as mock_load, \
             patch("aether_data_spine.emit.search_granules") as mock_search:

            # Mock event
            mock_event = Mock()
            mock_event.location = Mock(lat=32.25, lon=-104.15)
            mock_event.date_range = Mock(
                start=Mock(isoformat=lambda: "2022-08-01T00:00:00Z"),
                end=Mock(isoformat=lambda: "2022-09-13T23:59:59Z"),
            )
            mock_load.return_value = mock_event

            # Mock empty search results
            mock_search.return_value = []

            with pytest.raises(ValueError, match="No EMIT granules found"):
                reproduce.reproduce_event("test_event")

    def test_reproduce_event_missing_location(self) -> None:
        """Test reproduce with event missing location."""
        with patch("aether_cli.reproduce.load_event") as mock_load:
            mock_event = Mock(spec=[])  # No attributes
            mock_load.return_value = mock_event

            with pytest.raises(ValueError, match="missing location or date_range"):
                reproduce.reproduce_event("test_event")


@pytest.mark.integration
class TestReproduceIntegration:
    """Integration tests for the reproduce command.

    These tests are skipped by default. Run with: pytest -m integration
    """

    def test_reproduce_permian_basin_event_real(self, tmp_path: Path) -> None:
        """Test reproducing the Permian Basin event with real data.

        WARNING: This downloads real EMIT data (~100+ MB).
        """
        pytest.skip("Skipped by default to avoid large downloads")

        from aether_data_spine import emit

        try:
            emit.authenticate()
        except RuntimeError:
            pytest.skip("NASA Earthdata credentials not configured")

        output_path = tmp_path / "permian_basin_2022_plume.png"

        # This should download, cache, and render
        result_path = reproduce.reproduce_event(
            "permian_basin_2022",
            output_path=output_path,
            force=False,
        )

        assert result_path.exists()
        assert result_path == output_path
