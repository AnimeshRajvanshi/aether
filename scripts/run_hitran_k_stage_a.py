"""Sprint 6 Stage A: generate our independent k and validate its SHAPE vs NASA.

Generates the HITRAN-derived methane unit absorption spectrum on the Goturdepe
granule's EMIT grid, commits it with provenance, and reports the spectral-shape
correlation against NASA's per-granule target file — used ONLY as a cross-check,
never as an input to our k. Stops here (no end-to-end run; that is Stage B).

Run from the repo root:  uv run python scripts/run_hitran_k_stage_a.py
"""

from __future__ import annotations

# Imports are intentionally placed after warnings.filterwarnings() and
# matplotlib.use("Agg") below, which must run before pyplot is imported; exempt
# only E402 here.
# ruff: noqa: E402
import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from aether_data_spine import emit_l1b
from aether_detection import hitran_k, target_signature
from aether_detection.constants import MF_SPECTRAL_WINDOWS_NM
from aether_detection.constants import (
    TURKMENISTAN_GOTURDEPE_2022_08_15_TARGET_FILENAME as TARGET_FILE,
)
from aether_detection.target_signature import select_band_indices

EVENT_ID = "turkmenistan_goturdepe_2022_08_15"
REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("~/.aether_cache").expanduser()
OUT_DIR = REPO_ROOT / "stage_a_outputs" / EVENT_ID / "hitran_k"

# Scene surface state — the committed ERA5 values used by Stage B (our own input).
Q_ESTIMATE = REPO_ROOT / "stage_b_outputs" / EVENT_ID / "q_estimate.json"


def _granule_geometry(ds) -> tuple[float, float]:
    """Scene-mean solar + view zenith (deg) from the OBS cube. EMIT OBS band order:
    index 2 = to-sensor zenith, index 4 = to-sun (solar) zenith."""
    a = np.asarray(ds["obs_obs"].values, dtype=np.float64)
    a = np.moveaxis(a, int(np.argmin(a.shape)), -1)

    def mean_band(i: int) -> float:
        v = a[..., i].ravel()
        v = v[np.isfinite(v) & (v > -900)]
        return float(np.mean(v))

    return mean_band(4), mean_band(2)  # (solar_zenith, view_zenith)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    q = json.loads(Q_ESTIMATE.read_text())
    p_pa = float(q["surface_pressure_pa"])
    t_k = float(q["surface_temperature_k"])

    ds = emit_l1b.load_l1b_from_cache(sorted((CACHE / "emit_l1b").glob("*.zarr"))[0])
    _, wl, fwhm = emit_l1b.get_radiance_cube(ds)
    sza, vza = _granule_geometry(ds)
    print(f"granule geometry: solar_zenith={sza:.2f} deg, view_zenith={vza:.2f} deg")
    print(f"surface state (ERA5): P={p_pa:.0f} Pa, T={t_k:.1f} K")

    res = hitran_k.generate_k(
        wl,
        fwhm,
        solar_zenith_deg=sza,
        view_zenith_deg=vza,
        surface_pressure_pa=p_pa,
        surface_temperature_k=t_k,
    )

    # --- commit our k: drop-in 285-row "index wavelength_nm value" format + npz ---
    idx = np.arange(wl.size)
    np.savetxt(
        OUT_DIR / "hitran_ch4_target",
        np.column_stack([idx, wl, res.k]),
        fmt=["%d", "%.6f", "%.8e"],
        header="index  wavelength_nm  k_per_ppm_m  (independent HITRAN; NASA file NOT used)",
    )
    np.savez(OUT_DIR / "hitran_k.npz", wavelengths_nm=wl, fwhm_nm=fwhm, k=res.k)
    # tracked JSON (the .npz is gitignored under stage_a_outputs/**/*.npz): carries
    # the granule SRF + our k so reproducibility is checkable from committed data.
    (OUT_DIR / "hitran_k.json").write_text(
        json.dumps(
            {"wavelengths_nm": wl.tolist(), "fwhm_nm": fwhm.tolist(), "k": res.k.tolist()}
        )
    )

    # --- Validation A: spectral SHAPE vs NASA target, over the exact 49 MF bands ---
    target_path = CACHE / "emit_targets" / TARGET_FILE
    _nasa_wl, nasa_k = target_signature.load_unit_absorption_spectrum(target_path)
    mf_bands = select_band_indices(wl, MF_SPECTRAL_WINDOWS_NM)
    ours = res.k[mf_bands]
    theirs = nasa_k[mf_bands]
    r = float(np.corrcoef(ours, theirs)[0, 1])
    # rank correlation too (shape robustness, amplitude-convention-free)
    from scipy.stats import spearmanr

    rho = float(spearmanr(ours, theirs).statistic)
    print(f"\nSHAPE validation over {mf_bands.size} MF-window bands (2137-2493 nm):")
    print(f"  Pearson  r = {r:.4f}   (cross-check ONLY; NASA file not used to build k)")
    print(f"  Spearman ρ = {rho:.4f}")

    # --- overlay plot (normalized shapes; amplitudes differ by convention) ---
    def norm(x: np.ndarray) -> np.ndarray:
        return x / np.max(np.abs(x))

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    ax[0].plot(
        wl[mf_bands], norm(theirs), "o-", color="#888", lw=1.4, ms=4, label="NASA target (norm)"
    )
    ax[0].plot(
        wl[mf_bands], norm(ours), "o-", color="#ff9d3c", lw=1.4, ms=4, label="Ours · HITRAN (norm)"
    )
    ax[0].set_xlabel("wavelength (nm)")
    ax[0].set_ylabel("normalized unit absorption k")
    ax[0].set_title(f"Spectral shape overlay — Pearson r = {r:.3f}")
    ax[0].legend()
    ax[0].grid(alpha=0.3)
    ax[1].scatter(norm(theirs), norm(ours), c="#35d6c3", s=18)
    ax[1].plot([-1, 1], [-1, 1], "k--", lw=0.8, alpha=0.5)
    ax[1].set_xlabel("NASA target k (norm)")
    ax[1].set_ylabel("our HITRAN k (norm)")
    ax[1].set_title(f"Spearman ρ = {rho:.3f}")
    ax[1].grid(alpha=0.3)
    fig.suptitle("Sprint 6 Stage A — independent HITRAN k vs NASA target (shape cross-check only)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "hitran_k_vs_nasa.png", dpi=130)

    report = {
        "event_id": EVENT_ID,
        "stage": "A — k generation + spectral-shape validation",
        "shape_pearson_r_vs_nasa": r,
        "shape_spearman_rho_vs_nasa": rho,
        "n_mf_window_bands": int(mf_bands.size),
        "nasa_target_role": "validation cross-check only; NOT an input to k",
        **res.provenance,
    }
    (OUT_DIR / "hitran_k_stage_a_report.json").write_text(json.dumps(report, indent=2))
    res.provenance["shape_pearson_r_vs_nasa"] = r
    (OUT_DIR / "hitran_k_provenance.json").write_text(json.dumps(res.provenance, indent=2))
    print(
        f"\nWrote {OUT_DIR.relative_to(REPO_ROOT)}/ : hitran_ch4_target, hitran_k.npz, "
        "hitran_k_vs_nasa.png, report + provenance"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
