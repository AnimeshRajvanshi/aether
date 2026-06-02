"""Aether Data Spine - Ingestion, normalization, caching for planetary monitoring datasets."""

__version__ = "0.1.0"

from aether_data_spine import emit, emit_l1b, emit_l2a_mask, era5

__all__ = ["emit", "emit_l1b", "emit_l2a_mask", "era5"]
