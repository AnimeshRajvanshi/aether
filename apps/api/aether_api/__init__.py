"""Aether dashboard API.

A thin FastAPI service that reads committed Stage A/B outputs and benchmark
events from disk and serves them as clean JSON + georeferenced image assets.
No values are hardcoded here — every number traces to a file under
``stage_a_outputs/``, ``stage_b_outputs/``, ``eval/benchmark/`` or the derived
``assets/`` rasters. See ``loaders.py`` for the field-by-field mapping.
"""

__all__ = ["__version__"]

__version__ = "0.3.0"
