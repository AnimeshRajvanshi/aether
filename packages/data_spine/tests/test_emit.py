"""Unit tests for EMIT data access module."""

from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest
import xarray as xr
from aether_data_spine import emit


class TestEmitModule:
    """Test suite for EMIT module functions."""

    def test_authenticate_success(self) -> None:
        """Test successful NASA Earthdata authentication."""
        with patch("earthaccess.login") as mock_login:
            mock_auth = Mock()
            mock_auth.authenticated = True
            mock_login.return_value = mock_auth

            # Should not raise
            emit.authenticate()
            mock_login.assert_called_once()

    def test_authenticate_failure(self) -> None:
        """Test failed NASA Earthdata authentication."""
        with patch("earthaccess.login") as mock_login:
            mock_auth = Mock()
            mock_auth.authenticated = False
            mock_login.return_value = mock_auth

            with pytest.raises(RuntimeError, match="authentication failed"):
                emit.authenticate()

    def test_search_granules(self) -> None:
        """Test searching for EMIT granules."""
        with patch("earthaccess.search_data") as mock_search:
            mock_granules = [
                {
                    "umm": {
                        "GranuleUR": "EMIT_L2B_CH4ENH_001_20220825T123456_2222105_001",
                        "TemporalExtent": {
                            "RangeDateTime": {
                                "BeginningDateTime": "2022-08-25T12:34:56Z",
                                "EndingDateTime": "2022-08-25T12:45:00Z",
                            }
                        },
                    }
                }
            ]
            mock_search.return_value = mock_granules

            results = emit.search_granules(
                lat=32.25,
                lon=-104.15,
                date_start="2022-08-01",
                date_end="2022-09-13",
            )

            assert len(results) == 1
            assert results[0]["umm"]["GranuleUR"] == mock_granules[0]["umm"]["GranuleUR"]

            # Verify earthaccess.search_data was called with correct params
            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args[1]
            assert call_kwargs["concept_id"] == emit.EMITL2BCH4ENH_CONCEPT_ID
            assert call_kwargs["temporal"] == ("2022-08-01", "2022-09-13")
            assert call_kwargs["point"] == (-104.15, 32.25)  # Note: lon, lat order

    def test_search_granules_no_results(self) -> None:
        """Test search with no matching granules."""
        with patch("earthaccess.search_data") as mock_search:
            mock_search.return_value = []

            results = emit.search_granules(
                lat=0.0,
                lon=0.0,
                date_start="2022-01-01",
                date_end="2022-01-02",
            )

            assert len(results) == 0

    def test_granule_to_cache_key(self) -> None:
        """Test cache key generation from granule."""
        granule = {
            "umm": {
                "GranuleUR": "EMIT_L2B_CH4ENH_001_20220825T123456_2222105_001",
            }
        }

        key = emit._granule_to_cache_key(granule)

        # Should be a 16-character hex string
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)

        # Same granule should produce same key (deterministic)
        key2 = emit._granule_to_cache_key(granule)
        assert key == key2

        # Different granule should produce different key
        granule2 = {
            "umm": {
                "GranuleUR": "EMIT_L2B_CH4ENH_001_20220826T123456_2222106_001",
            }
        }
        key3 = emit._granule_to_cache_key(granule2)
        assert key != key3

    def test_get_cache_path(self, tmp_path: Path) -> None:
        """Test cache path generation."""
        granule = {
            "umm": {
                "GranuleUR": "EMIT_L2B_CH4ENH_001_20220825T123456_2222105_001",
            }
        }

        cache_path = emit._get_cache_path(granule, tmp_path)

        # Should be in the tmp_path directory
        assert cache_path.parent == tmp_path

        # Should end with .zarr
        assert cache_path.suffix == ".zarr"

        # Should be deterministic
        cache_path2 = emit._get_cache_path(granule, tmp_path)
        assert cache_path == cache_path2

    def test_load_from_cache(self, tmp_path: Path) -> None:
        """Test loading a cached Zarr dataset."""
        # Create a mock Zarr dataset
        ds = xr.Dataset(
            {
                "ch4_enhancement": xr.DataArray(
                    np.random.rand(10, 10),
                    dims=["y", "x"],
                    attrs={"units": "ppm m"},
                ),
                "ch4_uncertainty": xr.DataArray(
                    np.random.rand(10, 10),
                    dims=["y", "x"],
                    attrs={"units": "ppm m"},
                ),
            }
        )

        zarr_path = tmp_path / "test.zarr"
        ds.to_zarr(zarr_path, mode="w", consolidated=True)

        # Load it back
        loaded_ds = emit.load_from_cache(zarr_path)

        assert "ch4_enhancement" in loaded_ds.data_vars
        assert "ch4_uncertainty" in loaded_ds.data_vars
        assert loaded_ds["ch4_enhancement"].shape == (10, 10)

    def test_extract_ch4_enhancement(self) -> None:
        """Test extracting methane enhancement from a dataset."""
        ds = xr.Dataset(
            {
                "ch4_enhancement": xr.DataArray(
                    np.random.rand(10, 10),
                    dims=["y", "x"],
                    attrs={"units": "ppm m"},
                ),
            }
        )

        ch4_enh = emit.extract_ch4_enhancement(ds)

        assert isinstance(ch4_enh, xr.DataArray)
        assert ch4_enh.shape == (10, 10)
        assert ch4_enh.attrs["units"] == "ppm m"

    def test_build_provenance(self, tmp_path: Path) -> None:
        """Test building provenance for an EMIT observation."""
        granule = {
            "umm": {
                "GranuleUR": "EMIT_L2B_CH4ENH_001_20220825T123456_2222105_001",
                "TemporalExtent": {
                    "RangeDateTime": {
                        "BeginningDateTime": "2022-08-25T12:34:56Z",
                        "EndingDateTime": "2022-08-25T12:45:00Z",
                    }
                },
            }
        }

        cache_path = tmp_path / "test.zarr"

        prov = emit.build_provenance(granule, cache_path)

        assert prov.source == "EMITL2BCH4ENH.002"
        assert prov.source_id == "EMIT_L2B_CH4ENH_001_20220825T123456_2222105_001"
        assert prov.pipeline is None
        assert prov.pipeline_version is None
        assert prov.parents == []
        assert prov.notes is not None
        assert "LP DAAC" in prov.notes
        assert str(cache_path) in prov.notes


@pytest.mark.integration
class TestEmitIntegration:
    """Integration tests that hit real NASA Earthdata endpoints.

    These tests are skipped by default. Run with: pytest -m integration

    Prerequisites:
    - Valid NASA Earthdata Login credentials in ~/.netrc
    - Network connectivity
    """

    def test_authenticate_real(self) -> None:
        """Test real authentication with NASA Earthdata.

        This requires valid credentials in ~/.netrc.
        """
        try:
            emit.authenticate()
        except RuntimeError:
            pytest.skip("NASA Earthdata credentials not configured")

    def test_search_real_permian_basin(self) -> None:
        """Test searching for the real Permian Basin plume granules.

        This hits the real CMR API.
        """
        try:
            emit.authenticate()
        except RuntimeError:
            pytest.skip("NASA Earthdata credentials not configured")

        # Search for Permian Basin event
        granules = emit.search_granules(
            lat=32.25,
            lon=-104.15,
            date_start="2022-08-01",
            date_end="2022-09-13",
        )

        # EMIT coverage is opportunistic; may or may not have granules
        # Just verify the search completes without error
        assert isinstance(granules, list)

    def test_download_and_cache_real(self, tmp_path: Path) -> None:
        """Test downloading and caching a real EMIT granule.

        WARNING: This downloads ~100+ MB of data. Only run manually.
        """
        pytest.skip("Skipped by default to avoid large downloads")

        try:
            emit.authenticate()
        except RuntimeError:
            pytest.skip("NASA Earthdata credentials not configured")

        granules = emit.search_granules(
            lat=32.25,
            lon=-104.15,
            date_start="2022-08-01",
            date_end="2022-09-13",
        )

        if not granules:
            pytest.skip("No granules found for this location/date")

        cache_path = emit.download_and_cache(granules[0], cache_dir=tmp_path)

        assert cache_path.exists()
        assert cache_path.suffix == ".zarr"

        # Load and verify
        ds = emit.load_from_cache(cache_path)
        assert "ch4_enhancement" in ds.data_vars
