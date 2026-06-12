"""Hypothesis engine v2 — multi-factor heat attribution (Sprint 9 Stage C).

Generalizes the Sprint 4 source-attribution machinery from "which facility"
to "which physical factors, with what weight" — ported, not forked:
deterministic templating from computed values, weighted score components with
rationales, qualitative tiers with a ceiling, assumptions,
counter-considerations, and falsification per factor.

Three gate rules are structural here (ADR 0005):

1. **No-fabrication-for-factors:** every factor binds to computed
   ``Diagnostic``s (schema-enforced non-empty). No diagnostic, no factor.
2. **Urban fabric argues from this event's evidence:** the measured daytime
   surface UHI is NEGATIVE (committed uhi.json), so urban heat is carried as
   COUNTER_EVIDENCE at the observed time — never listed as a daytime warming
   factor — with the nighttime/air-temperature role explicitly unassessed.
3. **Attribution boundary:** the engine ranks physical contributing factors.
   Probabilistic anthropogenic event attribution is out of scope to compute;
   the published WWA/Zachariah result appears ONLY as cited external evidence
   and never enters factor scores.

Reproducibility split: ``compute_diagnostics`` (cache-reading, runner-only)
writes the committed ``diagnostics.json``; ``build_factor_hypothesis_set`` is
a PURE function of that committed dict, so the regen guard re-derives the
committed ``factor_hypotheses.json`` byte-identically offline.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

from aether_causal.schema import (
    ConfidenceTier,
    Diagnostic,
    EvidenceItem,
    FactorHypothesis,
    FactorHypothesisSet,
    FactorRole,
    ScoreComponent,
    SourceRef,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Warming-contributor tiers are CAPPED at MODERATE: diagnostics rank
# co-occurring factors but cannot establish causal separation without
# counterfactual experiments (out of scope). HIGH is reserved-and-unearned,
# mirroring FAC_CEILING / the VALIDATED-tier reservation.
FACTOR_CEILING = ConfidenceTier.MODERATE
# Two factors whose scores differ by less than this are NOT discriminated:
# the gap is inside the resolving power of heuristic, co-varying diagnostics.
DISCRIMINATION_RESOLUTION = 0.15

_TIER_ORDER = [
    ConfidenceTier.HIGH,
    ConfidenceTier.MODERATE,
    ConfidenceTier.LOW,
    ConfidenceTier.INSUFFICIENT,
]


def _band(score: float) -> ConfidenceTier:
    if score >= 0.75:
        return ConfidenceTier.HIGH
    if score >= 0.5:
        return ConfidenceTier.MODERATE
    if score >= 0.25:
        return ConfidenceTier.LOW
    return ConfidenceTier.INSUFFICIENT


def _capped(score: float) -> tuple[ConfidenceTier, bool]:
    band = _band(score)
    capped = _TIER_ORDER.index(band) < _TIER_ORDER.index(FACTOR_CEILING)
    return (FACTOR_CEILING if capped else band), capped


# --------------------------------------------------------------------------- #
# Diagnostics computation (runner-only; cache + committed Stage B artifacts)
# --------------------------------------------------------------------------- #

HEAT_FACTOR_EVENTS: dict[str, dict[str, Any]] = {
    "india_nw_heatwave_2022_04": {
        "window": ("2022-04-02", "2022-04-11"),
        "soil_days": ("2022-03-01", "2022-04-11"),
        "antecedent_days": ("2022-03-01", "2022-03-31"),
        "clim_years": (1991, 2020),
    },
}


def _percentile_rank(value: float, samples: list[float]) -> float:
    """Fraction of samples strictly below `value` (0..1)."""
    if not samples:
        raise ValueError("empty climatology sample")
    return sum(1 for s in samples if s < value) / len(samples)


def _rarity_above_median(pct: float) -> float:
    """Map a percentile to rarity support: 0 at/below median, 1 at the extreme.

    Scores must reward how UNUSUAL a diagnostic is, not its climatological
    state — a 57th-percentile value is near normal and earns ~0.14, not 0.57.
    """
    return max(0.0, 2.0 * (pct - 0.5))


def compute_diagnostics(
    event_id: str,
    cache_root: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """All factor diagnostics for one event, from cache + committed artifacts.

    Returns the dict that the runner commits as ``diagnostics.json``. Imports
    numpy locally so the pure builder stays importable without the scientific
    stack.
    """
    import numpy as np

    cfg = HEAT_FACTOR_EVENTS[event_id]
    cache = (cache_root or Path("~/.aether_cache").expanduser()) / "sprint9_heat_stage_c"
    cache_b = (cache_root or Path("~/.aether_cache").expanduser()) / "sprint9_heat_stage_b"
    root = repo_root or _REPO_ROOT
    y0, y1 = cfg["clim_years"]
    clim_years = list(range(y0, y1 + 1))

    grid = np.load(cache_b / f"era5_grid_{event_id}.npz")
    lats, lons, land = grid["lats"], grid["lons"], grid["land"]
    w_all = np.cos(np.deg2rad(lats))[:, None] * np.ones((1, lons.size))
    w_land = np.where(land, w_all, 0.0)

    def rmean(field2d: np.ndarray, weights: np.ndarray) -> float:
        return float((field2d * weights).sum() / weights.sum())

    def load_var(var: str, year: int) -> np.ndarray:
        return np.asarray(np.load(cache / f"{var}_{year}.npz")["field"])

    out: dict[str, Any] = {"event_id": event_id, "clim_years": [y0, y1]}

    # ---- F1 synoptic: z500 ----
    z = np.load(cache / "z500_clim_regional.npz")
    clim_daily: np.ndarray = np.asarray(z["regional_mean_m"])  # (30, 10)
    clim_window_means = clim_daily.mean(axis=1)  # (30,)
    g2022 = load_var("geopotential", 2022) / 9.80665  # (10, ny, nx) meters
    z_2022_daily = [rmean(g2022[i], w_all) for i in range(g2022.shape[0])]
    z_2022_window = float(np.mean(z_2022_daily))
    pooled = clim_daily.ravel().tolist()
    p90 = float(np.percentile(clim_daily.ravel(), 90))

    # Cross-store systematic: the 2022 value comes from the 0.25-deg store but
    # the climatology from the 1.5-deg conservative store. Measure the offset
    # on overlap years present in BOTH (v3 fetch + the climatology file) and
    # correct the 2022 value before ranking — otherwise the percentile would
    # carry a silent regridding bias.
    clim_year_list = np.asarray(z["years"]).tolist()
    offsets = []
    for oy in (2019, 2020):
        path = cache / f"geopotential_{oy}.npz"
        if path.exists() and oy in clim_year_list:
            gov = np.asarray(np.load(path)["field"]) / 9.80665
            v3_mean = float(np.mean([rmean(gov[i], w_all) for i in range(gov.shape[0])]))
            coarse_mean = float(clim_window_means[clim_year_list.index(oy)])
            offsets.append(v3_mean - coarse_mean)
    if not offsets:
        raise FileNotFoundError(
            "no overlap years for the z500 cross-store offset check — fetch "
            "geopotential 2019/2020 first (the percentile must not carry a "
            "silent regridding bias)"
        )
    offset = float(np.mean(offsets))
    z_2022_corrected = z_2022_window - offset
    p90_corr = p90 + offset  # compare daily v3 values against offset-shifted p90
    out["z500"] = {
        "window_mean_2022_m": round(z_2022_window, 1),
        "cross_store_offset_m": round(offset, 1),
        "cross_store_offset_per_year_m": [round(o, 1) for o in offsets],
        "window_mean_2022_corrected_m": round(z_2022_corrected, 1),
        "clim_window_mean_m": round(float(clim_window_means.mean()), 1),
        "clim_window_std_m": round(float(clim_window_means.std()), 1),
        "anomaly_m": round(z_2022_corrected - float(clim_window_means.mean()), 1),
        "anomaly_uncorrected_m": round(z_2022_window - float(clim_window_means.mean()), 1),
        "percentile_vs_30_window_means": round(
            _percentile_rank(z_2022_corrected, clim_window_means.tolist()), 3
        ),
        "days_above_pooled_p90": int(sum(1 for v in z_2022_daily if v > p90_corr)),
        "n_window_days": len(z_2022_daily),
        "pooled_day_percentile_of_window_mean": round(
            _percentile_rank(z_2022_corrected, pooled), 3
        ),
        "grids": "2022 from 0.25-deg v3 (regional mean); climatology from the "
        "1.5-deg conservative store; the measured cross-store offset (overlap "
        "years 2019-2020) is subtracted from the 2022 value before ranking; "
        "06:00 UTC samples",
    }

    # ---- F2 soil moisture (swvl1, 0-7 cm; ERA5 land-surface MODEL product) ----
    soil_d0 = date.fromisoformat(cfg["soil_days"][0])
    ant_d1 = date.fromisoformat(cfg["antecedent_days"][1])
    win_d0 = date.fromisoformat(cfg["window"][0])
    n_ant = (ant_d1 - soil_d0).days + 1  # March indices [0, n_ant)
    win_i0 = (win_d0 - soil_d0).days

    def soil_means(year: int) -> tuple[float, float]:
        f = load_var("volumetric_soil_water_layer_1", year)
        ant = float(np.mean([rmean(f[i], w_land) for i in range(n_ant)]))
        win = float(np.mean([rmean(f[i], w_land) for i in range(win_i0, f.shape[0])]))
        return ant, win

    clim_soil = [soil_means(y) for y in clim_years]
    ant_2022, win_2022 = soil_means(2022)
    ant_clim = [a for a, _ in clim_soil]
    win_clim = [b for _, b in clim_soil]
    out["soil_moisture"] = {
        "antecedent_march_2022_m3m3": round(ant_2022, 4),
        "antecedent_clim_mean_m3m3": round(float(np.mean(ant_clim)), 4),
        "antecedent_percentile": round(_percentile_rank(ant_2022, ant_clim), 3),
        "window_2022_m3m3": round(win_2022, 4),
        "window_clim_mean_m3m3": round(float(np.mean(win_clim)), 4),
        "window_percentile": round(_percentile_rank(win_2022, win_clim), 3),
        "layer": "volumetric_soil_water_layer_1 (0-7 cm), bbox land cells, 06 UTC",
    }

    # ---- F3 advection: 10 m winds ----
    def wind_means(year: int) -> tuple[float, float]:
        u = load_var("10m_u_component_of_wind", year)
        v = load_var("10m_v_component_of_wind", year)
        return (
            float(np.mean([rmean(u[i], w_all) for i in range(u.shape[0])])),
            float(np.mean([rmean(v[i], w_all) for i in range(v.shape[0])])),
        )

    uv_clim = [wind_means(y) for y in clim_years]
    u_2022, v_2022 = wind_means(2022)
    u_c = float(np.mean([u for u, _ in uv_clim]))
    v_c = float(np.mean([v for _, v in uv_clim]))
    speed_2022 = math.hypot(u_2022, v_2022)
    from_dir_2022 = (math.degrees(math.atan2(-u_2022, -v_2022))) % 360.0
    from_dir_clim = (math.degrees(math.atan2(-u_c, -v_c))) % 360.0
    out["winds"] = {
        "window_mean_u_ms": round(u_2022, 2),
        "window_mean_v_ms": round(v_2022, 2),
        "window_mean_speed_ms": round(speed_2022, 2),
        "window_from_direction_deg": round(from_dir_2022, 1),
        "clim_mean_u_ms": round(u_c, 2),
        "clim_mean_v_ms": round(v_c, 2),
        "clim_from_direction_deg": round(from_dir_clim, 1),
        "anomaly_vector_ms": [round(u_2022 - u_c, 2), round(v_2022 - v_c, 2)],
        "anomaly_magnitude_ms": round(math.hypot(u_2022 - u_c, v_2022 - v_c), 2),
        "convention": "meteorological FROM-direction; bbox area mean, 06 UTC",
    }

    # ---- F4 humidity: 2 m dewpoint ----
    def dew_mean(year: int) -> float:
        f = load_var("2m_dewpoint_temperature", year)
        return float(np.mean([rmean(f[i], w_land) for i in range(f.shape[0])]))

    dew_clim = [dew_mean(y) for y in clim_years]
    dew_2022 = dew_mean(2022)
    out["dewpoint"] = {
        "window_mean_2022_k": round(dew_2022, 2),
        "clim_mean_k": round(float(np.mean(dew_clim)), 2),
        "anomaly_k": round(dew_2022 - float(np.mean(dew_clim)), 2),
        "percentile": round(_percentile_rank(dew_2022, dew_clim), 3),
        "scope": "bbox land mean, 06 UTC — severity framing only, not a warming driver",
    }

    # ---- F5 urban fabric: from the COMMITTED Stage B UHI artifact ----
    uhi = json.loads(
        (root / "stage_b_outputs" / event_id / "uhi.json").read_text()
    )
    sens = uhi["sensitivities"]
    out["uhi"] = {
        "window_mean_uhi_k": uhi["window_mean_uhi_k"],
        "window_std_uhi_k": uhi["window_std_uhi_k"],
        "n_valid_days": uhi["n_valid_days"],
        "sensitivity_range_k": [
            min(v["mean_uhi_k"] for v in sens.values()),
            max(v["mean_uhi_k"] for v in sens.values()),
        ],
        "observed_time": "Terra ~10:30 local snapshot (the only observed daytime LST time)",
        "source_artifact": f"stage_b_outputs/{event_id}/uhi.json",
    }

    out["provenance"] = {
        "era5_v3": "gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3",
        "era5_coarse": (
            "gs://gcp-public-data-arco-era5/ar/"
            "1959-2022-6h-240x121_equiangular_with_poles_conservative.zarr"
        ),
        "uhi_artifact": f"stage_b_outputs/{event_id}/uhi.json",
        "fetch_script": "scripts/sprint9_fetch_factors.py",
        "sample_hour_utc": "06 (11:30 IST)",
    }
    return out


# --------------------------------------------------------------------------- #
# Pure builder (deterministic from the committed diagnostics dict)
# --------------------------------------------------------------------------- #


def build_factor_hypothesis_set(event_id: str, diag: dict[str, Any]) -> FactorHypothesisSet:
    """Deterministic factor hypotheses from committed diagnostics. Pure."""
    z = diag["z500"]
    soil = diag["soil_moisture"]
    winds = diag["winds"]
    dew = diag["dewpoint"]
    uhi = diag["uhi"]

    def src(name: str) -> SourceRef:
        return SourceRef(
            dataset=diag["provenance"]["era5_v3"],
            locator=f"attribution_outputs/{event_id}/diagnostics.json#{name}",
        )

    # ---------------- F1 synoptic ridge ----------------
    ridge_pct = float(z["percentile_vs_30_window_means"])
    persistence = z["days_above_pooled_p90"] / z["n_window_days"]
    f1_components = [
        ScoreComponent(
            name="ridge_anomaly_percentile",
            value=round(ridge_pct, 3),
            weight=0.6,
            rationale=(
                f"window-mean regional z500 ({z['window_mean_2022_corrected_m']} m "
                f"corrected, anomaly +{z['anomaly_m']} m) ranks at the "
                f"{ridge_pct:.0%} percentile of the "
                f"{diag['clim_years'][0]}-{diag['clim_years'][1]} same-window means"
            ),
        ),
        ScoreComponent(
            name="ridge_persistence",
            value=round(persistence, 3),
            weight=0.4,
            rationale=(
                f"{z['days_above_pooled_p90']} of {z['n_window_days']} window days "
                "exceed the pooled climatological p90 of daily regional z500"
            ),
        ),
    ]
    f1_score = round(sum(c.contribution for c in f1_components), 4)
    f1_tier, f1_capped = _capped(f1_score)
    f1 = FactorHypothesis(
        id="F1",
        rank=1,  # placeholder; re-ranked after sorting
        factor_name="Persistent synoptic ridge / anticyclonic mid-troposphere",
        role=FactorRole.WARMING_CONTRIBUTOR,
        claim=(
            f"A persistent mid-tropospheric ridge sat over the region: window-mean "
            f"regional 500 hPa height {z['window_mean_2022_corrected_m']} m "
            f"(cross-store-corrected from {z['window_mean_2022_m']} m) vs climatology "
            f"{z['clim_window_mean_m']} m (+{z['anomaly_m']} m, "
            f"{ridge_pct:.0%} percentile of 30 same-window years; "
            f"{z['days_above_pooled_p90']}/{z['n_window_days']} days above the pooled "
            "p90). Anticyclonic subsidence and clear skies under such ridges are an "
            "established heatwave driver; the diagnostic establishes presence and "
            "rarity, not a quantified temperature contribution."
        ),
        confidence_tier=f1_tier,
        confidence_rationale=(
            f"Heuristic score {f1_score:.2f}"
            + (
                f" (band above ceiling, CAPPED to {FACTOR_CEILING.value})"
                if f1_capped
                else ""
            )
            + " — the ridge is present, rare, and persistent by diagnostic, but "
            "diagnostics cannot separate its contribution from the co-varying "
            "land-surface state (see headline)."
        ),
        score=min(f1_score, 1.0),
        score_components=f1_components,
        diagnostics=[
            Diagnostic(
                name="z500_window_mean_anomaly",
                value=float(z["anomaly_m"]),
                unit="m",
                definition="2022 window-mean regional z500 minus 1991-2020 same-window mean",
                source=src("z500"),
            ),
            Diagnostic(
                name="z500_percentile_vs_30_window_means",
                value=ridge_pct,
                unit="fraction",
                definition="rank of the 2022 window mean among 30 climatology window means",
                source=src("z500"),
            ),
            Diagnostic(
                name="z500_days_above_pooled_p90",
                value=float(z["days_above_pooled_p90"]),
                unit="days",
                definition="window days with daily regional z500 above the pooled clim p90",
                source=src("z500"),
            ),
        ],
        evidence=[
            EvidenceItem(
                kind="reanalysis_diagnostic",
                statement=(
                    f"Regional z500 anomaly +{z['anomaly_m']} m "
                    f"({z['clim_window_std_m']} m climatological std of window means)."
                ),
                source=src("z500"),
            )
        ],
        assumptions=[
            "ERA5 z500 is well constrained by assimilated upper-air observations over "
            "South Asia (radiosondes, aircraft, satellites).",
            "The 2022 value (0.25-deg store) and the climatology (1.5-deg conservative "
            "store) are comparable as regional MEANS; conservative regridding preserves "
            "area means (cross-store caveat stated in diagnostics.json).",
            "06:00 UTC sampling represents the window's synoptic state (ridges evolve "
            "on multi-day timescales).",
        ],
        counter_considerations=[
            "Ridge presence co-occurs with (and is amplified by) dry land surfaces — "
            "presence does not apportion contribution.",
            "A single regional-mean index can under-represent ridge structure "
            "(amplitude vs extent).",
        ],
        falsification=(
            "Independent upper-air analyses (radiosonde geopotential heights) or a "
            "higher-resolution reanalysis showing no anomalous ridge over the region "
            "during the window would falsify the presence claim."
        ),
        generation_method="aether_causal.heat_factors v1 (deterministic templating)",
    )

    # ---------------- F2 antecedent dryness ----------------
    ant_dry = 1.0 - float(soil["antecedent_percentile"])
    win_dry = 1.0 - float(soil["window_percentile"])
    # Scores reward RARITY (distance above the median), not climatological
    # state: near-median antecedent moisture must not look like support.
    f2_components = [
        ScoreComponent(
            name="antecedent_dryness_rarity",
            value=round(_rarity_above_median(ant_dry), 3),
            weight=0.7,
            rationale=(
                f"March 2022 regional soil moisture {soil['antecedent_march_2022_m3m3']} "
                f"m3/m3 vs climatology {soil['antecedent_clim_mean_m3m3']} — dryness rank "
                f"{ant_dry:.0%} (rarity support {_rarity_above_median(ant_dry):.2f}: "
                "near-median antecedent moisture earns near zero)"
            ),
        ),
        ScoreComponent(
            name="window_dryness_rarity",
            value=round(_rarity_above_median(win_dry), 3),
            weight=0.3,
            rationale=(
                f"window soil moisture {soil['window_2022_m3m3']} vs climatology "
                f"{soil['window_clim_mean_m3m3']} — dryness rank {win_dry:.0%}; weighted "
                "low because in-window drying is partly the heat's own effect "
                "(concurrent, not preconditioning)"
            ),
        ),
    ]
    f2_score = round(sum(c.contribution for c in f2_components), 4)
    f2_tier, f2_capped = _capped(f2_score)
    if ant_dry >= 0.8:
        f2_precondition = (
            f"The land surface was anomalously pre-dried: March 2022 regional soil "
            f"moisture was drier than {ant_dry:.0%} of the 30 climatology Marches."
        )
    elif ant_dry >= 0.65:
        f2_precondition = (
            f"The land surface was modestly pre-dried (March dryness rank "
            f"{ant_dry:.0%} — above median but not extreme)."
        )
    else:
        f2_precondition = (
            f"The popular pre-dried-soil narrative is NOT supported by this "
            f"diagnostic: March 2022 regional soil moisture was near climatology "
            f"(dryness rank {ant_dry:.0%})."
        )
    # Falsification must target the COMMITTED position (the branch taken), not
    # the rejected prior (Stage C gate ruling 2).
    if ant_dry >= 0.65:
        f2_falsification = (
            "Independent soil-moisture observations (in-situ networks, satellite "
            "retrievals) showing normal-or-wetter antecedent soils over the region "
            "would overturn the preconditioning claim."
        )
    else:
        f2_falsification = (
            "Independent soil-moisture observations (in-situ networks, satellite "
            "retrievals) showing anomalously DRY antecedent soils over the region "
            "would overturn this against-prior finding (and would support the "
            "preconditioning narrative this diagnostic does not)."
        )
    f2 = FactorHypothesis(
        id="F2",
        rank=1,
        factor_name="Antecedent soil-moisture deficit (land-surface preconditioning)",
        role=FactorRole.WARMING_CONTRIBUTOR,
        claim=(
            f"{f2_precondition} In-window soil moisture was drier than "
            f"{win_dry:.0%} of years, but in-window drying is concurrent with — and "
            "plausibly caused by — the heat itself, so it cannot establish "
            "preconditioning. Dry soils amplify heat via suppressed evaporative "
            "cooling; for THIS event the antecedent diagnostic carries the "
            "preconditioning question, and it reads near-normal."
        ),
        confidence_tier=f2_tier,
        confidence_rationale=(
            f"Heuristic score {f2_score:.2f}"
            + (
                f" (band above ceiling, CAPPED to {FACTOR_CEILING.value})"
                if f2_capped
                else ""
            )
            + " — dryness is real by diagnostic, but ERA5 soil moisture is a model "
            "product and the factor co-varies with the ridge (see headline)."
        ),
        score=min(f2_score, 1.0),
        score_components=f2_components,
        diagnostics=[
            Diagnostic(
                name="antecedent_march_soil_moisture",
                value=float(soil["antecedent_march_2022_m3m3"]),
                unit="m3/m3",
                definition="March 2022 mean volumetric soil water (0-7 cm), bbox land",
                source=src("soil_moisture"),
            ),
            Diagnostic(
                name="antecedent_dryness_percentile",
                value=round(ant_dry, 3),
                unit="fraction",
                definition="1 - percentile of 2022 March soil moisture among 1991-2020",
                source=src("soil_moisture"),
            ),
        ],
        evidence=[
            EvidenceItem(
                kind="reanalysis_diagnostic",
                statement=(
                    f"Antecedent (March) and in-window soil moisture both anomalously "
                    f"low (drier than {ant_dry:.0%} / {win_dry:.0%} of climatology)."
                ),
                source=src("soil_moisture"),
            )
        ],
        assumptions=[
            "ERA5 volumetric soil water is a land-surface-model product, only weakly "
            "constrained by observations — treated as a physically consistent index, "
            "not a measurement.",
            "Layer 1 (0-7 cm) dryness is representative of the evaporative regime at "
            "event timescales.",
        ],
        counter_considerations=[
            "Soil dryness is partly CAUSED by the same circulation pattern (rainfall "
            "deficit under persistent ridging) — circularity with F1 is intrinsic and "
            "is why the engine does not claim discrimination.",
            "No in-situ or independent satellite soil-moisture diagnostic was computed "
            "in this stage (SMAP/ASCAT are out of the locked source list).",
        ],
        falsification=f2_falsification,
        generation_method="aether_causal.heat_factors v1 (deterministic templating)",
    )

    # ---------------- F3 advection ----------------
    from_dir = float(winds["window_from_direction_deg"])
    # Dry continental sector for NW India: flow FROM the west through north
    # (247.5..360 deg) crosses the Thar/Baluchistan arid zone.
    in_dry_sector = 247.5 <= from_dir <= 360.0
    anom_ratio = min(
        float(winds["anomaly_magnitude_ms"]) / max(float(winds["window_mean_speed_ms"]), 0.1),
        1.0,
    )
    # The factor is ANOMALOUS advection. Sector membership alone is the
    # climatological state over NW India (westerlies are normal) and must not
    # score — it is carried as a diagnostic, while the score follows the
    # anomaly magnitude.
    f3_components = [
        ScoreComponent(
            name="flow_anomaly_magnitude",
            value=round(anom_ratio, 3),
            weight=1.0,
            rationale=(
                f"wind anomaly vector magnitude {winds['anomaly_magnitude_ms']} m/s vs "
                f"window-mean speed {winds['window_mean_speed_ms']} m/s — how unusual "
                "the flow was; direction alone is climatology and earns nothing"
            ),
        ),
    ]
    f3_score = round(sum(c.contribution for c in f3_components), 4)
    f3_tier, f3_capped = _capped(f3_score)
    f3_reading = (
        "essentially climatological flow — no anomalous advective contribution "
        "is indicated"
        if anom_ratio < 0.5
        else "anomalously strong/shifted flow relative to climatology"
    )
    if anom_ratio < 0.5:
        f3_falsification = (
            "Back-trajectory analysis (e.g., HYSPLIT on reanalysis winds) "
            "demonstrating anomalously strong or persistent transport from the arid "
            "sector relative to climatology would overturn the "
            "no-anomalous-advection finding."
        )
    else:
        f3_falsification = (
            "Back-trajectory analysis showing air-mass origins outside the arid "
            "sector for most window days would overturn the anomalous-advection "
            "claim."
        )
    f3 = FactorHypothesis(
        id="F3",
        rank=1,
        factor_name="Low-level advection from the arid continental sector",
        role=FactorRole.WARMING_CONTRIBUTOR,
        claim=(
            f"Window-mean near-surface flow was FROM {from_dir:.1f} deg at "
            f"{winds['window_mean_speed_ms']} m/s, vs climatology FROM "
            f"{winds['clim_from_direction_deg']:.1f} deg — anomaly vector magnitude "
            f"{winds['anomaly_magnitude_ms']} m/s: {f3_reading}. The "
            f"{'arid-sector' if in_dry_sector else 'non-arid-sector'} direction is "
            "the climatological norm here and is reported as state, not as event "
            "evidence (no trajectory analysis in scope)."
        ),
        confidence_tier=f3_tier,
        confidence_rationale=(
            f"Heuristic score {f3_score:.2f}"
            + (f" (CAPPED to {FACTOR_CEILING.value})" if f3_capped else "")
            + " — a bulk vector diagnostic only; back-trajectories were not computed."
        ),
        score=min(f3_score, 1.0),
        score_components=f3_components,
        diagnostics=[
            Diagnostic(
                name="window_from_direction",
                value=round(from_dir, 1),
                unit="deg",
                definition="meteorological FROM-direction of the window-mean 10 m wind",
                source=src("winds"),
            ),
            Diagnostic(
                name="wind_anomaly_magnitude",
                value=float(winds["anomaly_magnitude_ms"]),
                unit="m/s",
                definition="magnitude of (2022 window-mean vector - climatology vector)",
                source=src("winds"),
            ),
        ],
        evidence=[
            EvidenceItem(
                kind="reanalysis_diagnostic",
                statement=(
                    f"Mean flow from {from_dir:.1f} deg vs climatological "
                    f"{winds['clim_from_direction_deg']:.1f} deg."
                ),
                source=src("winds"),
            )
        ],
        assumptions=[
            "A bbox-mean 10 m vector meaningfully summarizes low-level flow at "
            "synoptic scale (it averages over sea-breeze and orographic detail).",
            "The W-N sector proxies arid-source advection (Thar/Baluchistan) without "
            "an explicit trajectory model.",
        ],
        counter_considerations=[
            "10 m winds under a ridge are weak; advection may be secondary to "
            "subsidence + local heating.",
            "No air-mass trajectory analysis was computed — sector membership is a "
            "coarse proxy.",
        ],
        falsification=f3_falsification,
        generation_method="aether_causal.heat_factors v1 (deterministic templating)",
    )

    # ---------------- F4 humidity (severity framing) ----------------
    dry_pct = 1.0 - float(dew["percentile"])
    # Two-sided rarity: anomalous dryness OR humidity both make the framing
    # factor active; near-median humidity means it is NOT active for this event.
    humidity_rarity = max(_rarity_above_median(dry_pct), _rarity_above_median(1.0 - dry_pct))
    if dry_pct >= 0.8:
        f4_reading = f"The heat was anomalously DRY (dryness rank {dry_pct:.0%})"
        f4_framing = (
            "Low humidity reduces heat-index amplification relative to humid heat "
            "while increasing desiccation/fire stress."
        )
    elif dry_pct <= 0.2:
        f4_reading = f"The heat was anomalously HUMID (humidity rank {1 - dry_pct:.0%})"
        f4_framing = (
            "High humidity amplifies experienced severity (heat index) beyond the "
            "temperature anomaly itself."
        )
    else:
        f4_reading = (
            f"Airmass humidity was near climatology (dewpoint anomaly "
            f"{dew['anomaly_k']:+.2f} K, dryness rank {dry_pct:.0%})"
        )
        f4_framing = (
            "Neither a dry-heat mitigation nor a humid-heat amplification of "
            "experienced severity is indicated by this diagnostic — the framing "
            "factor is NOT active for this event at the sampled hour."
        )
    if dry_pct >= 0.8 or dry_pct <= 0.2:
        f4_falsification = (
            "Station humidity observations (dewpoint/wet-bulb) contradicting the "
            "anomalous-humidity diagnostic would overturn the framing claim."
        )
    else:
        f4_falsification = (
            "Station humidity observations (dewpoint/wet-bulb) showing an "
            "anomalously dry or anomalously humid airmass during the window would "
            "overturn the not-active finding."
        )
    f4_components = [
        ScoreComponent(
            name="humidity_anomaly_rarity",
            value=round(humidity_rarity, 3),
            weight=1.0,
            rationale=(
                f"window-mean 2 m dewpoint {dew['window_mean_2022_k']} K "
                f"({dew['anomaly_k']:+.2f} K vs climatology; dryness rank "
                f"{dry_pct:.0%}) — two-sided rarity above the median; near-median "
                "humidity earns near zero"
            ),
        ),
    ]
    f4_score = round(sum(c.contribution for c in f4_components), 4)
    f4 = FactorHypothesis(
        id="F4",
        rank=1,
        factor_name="Airmass humidity (severity framing, not a warming driver)",
        role=FactorRole.SEVERITY_FRAMING,
        claim=(
            f"{f4_reading}. {f4_framing} This factor frames experienced severity and "
            "is NOT ranked as a temperature driver."
        ),
        confidence_tier=(
            ConfidenceTier.LOW if humidity_rarity >= 0.25 else ConfidenceTier.INSUFFICIENT
        ),
        confidence_rationale=(
            "Severity-framing role (never a temperature driver): tier reflects "
            "whether the humidity diagnostic is anomalous enough to frame severity "
            "at all — near-median humidity grades INSUFFICIENT (not active)."
        ),
        score=min(f4_score, 1.0),
        score_components=f4_components,
        diagnostics=[
            Diagnostic(
                name="dewpoint_window_anomaly",
                value=float(dew["anomaly_k"]),
                unit="K",
                definition="2022 window-mean 2 m dewpoint minus 1991-2020 same-window mean",
                source=src("dewpoint"),
            ),
        ],
        evidence=[
            EvidenceItem(
                kind="reanalysis_diagnostic",
                statement=f"Dewpoint anomaly {dew['anomaly_k']:+.2f} K (dry airmass).",
                source=src("dewpoint"),
            )
        ],
        assumptions=[
            "ERA5 2 m dewpoint is adequate for a regional-mean dryness index "
            "(assimilation-constrained like t2m).",
        ],
        counter_considerations=[
            "Dryness interacts with the soil-moisture factor (same land-atmosphere "
            "coupling); it is not independent evidence.",
        ],
        falsification=f4_falsification,
        generation_method="aether_causal.heat_factors v1 (deterministic templating)",
    )

    # ---------------- F5 urban fabric (counter-evidence at observed time) ----
    uhi_k = float(uhi["window_mean_uhi_k"])
    assert uhi_k == uhi_k, "UHI diagnostic missing"
    f5 = FactorHypothesis(
        id="F5",
        rank=1,
        factor_name="Urban fabric (daytime surface signal NEGATIVE at the observed time)",
        role=FactorRole.COUNTER_EVIDENCE,
        claim=(
            f"The measured Delhi daytime SURFACE urban-rural delta during the window "
            f"is NEGATIVE: {uhi_k:+.2f} K (±{uhi['window_std_uhi_k']} K day-to-day, "
            f"n={uhi['n_valid_days']}; sign robust across sensitivity range "
            f"{uhi['sensitivity_range_k'][0]:+.2f}..{uhi['sensitivity_range_k'][1]:+.2f} K) "
            f"at {uhi['observed_time']}. The data therefore argues AGAINST urban heat "
            "as a daytime warming factor for this event at the only observed time — "
            "the urban core read COOLER than its dry rural surroundings. The "
            "nighttime and 2 m air-temperature urban roles are EXPLICITLY UNASSESSED: "
            "no diagnostic for them exists in this stack (no nighttime analysis, no "
            "intra-urban air-temperature network)."
        ),
        confidence_tier=ConfidenceTier.INSUFFICIENT,
        confidence_rationale=(
            "As a WARMING contributor: insufficient — the only computed diagnostic "
            "is counter-evidence at the observed time. As a measured negative daytime "
            "surface signal: the diagnostic itself is sign-robust (Stage B). The tier "
            "grades the warming role, not the measurement."
        ),
        score=0.0,
        score_components=[
            ScoreComponent(
                name="daytime_surface_uhi_support",
                value=0.0,
                weight=1.0,
                rationale=(
                    f"measured daytime surface UHI {uhi_k:+.2f} K is negative — zero "
                    "support for daytime urban warming; nighttime/air roles carry no "
                    "diagnostic and contribute no score in either direction"
                ),
            )
        ],
        diagnostics=[
            Diagnostic(
                name="window_mean_daytime_surface_uhi",
                value=uhi_k,
                unit="K",
                definition=(
                    "Delhi urban-core minus rural-ring MODIS LST, window mean, "
                    "Terra ~10:30 local (committed Stage B artifact)"
                ),
                source=SourceRef(
                    dataset="MOD11A1 v061 + ESA WorldCover v200 (Stage B)",
                    locator=uhi["source_artifact"],
                ),
            ),
        ],
        evidence=[
            EvidenceItem(
                kind="committed_artifact",
                statement=(
                    f"Stage B UHI analysis: {uhi_k:+.2f} ± {uhi['window_std_uhi_k']} K "
                    f"over {uhi['n_valid_days']} days; sign robust to all "
                    "pre-registered sensitivities; Landsat sign-agrees on 2 of 3 scenes."
                ),
                source=SourceRef(
                    dataset="stage_b_outputs (Sprint 9 Stage B, gate-approved)",
                    locator=uhi["source_artifact"],
                ),
                temporal_caveat=(
                    "Valid at the Terra ~10:30 local snapshot only — the single "
                    "observed daytime LST time; says nothing about night or 2 m air."
                ),
            )
        ],
        assumptions=[
            "The Stage B UHI definition (WorldCover masks, 20/20-40 km geometry) "
            "represents Delhi's urban fabric adequately at 1 km.",
            "Skin temperature is the relevant quantity for a *surface* urban signal "
            "(2 m air is a different quantity — cardinal rule 2).",
        ],
        counter_considerations=[
            "Urban heat islands are classically strongest at NIGHT and in 2 m air — "
            "neither was observed in this stack; absence of a daytime surface signal "
            "does not refute a nighttime/air urban contribution.",
            "One city (Delhi) is not the whole event region.",
        ],
        falsification=(
            "The committed daytime-surface finding would be OVERTURNED by an "
            "independent LST analysis of the same window (different masks, sensors, "
            "or QC) showing a positive daytime urban-rural delta. Separately, the "
            "UNASSESSED nighttime/air-temperature roles would be ESTABLISHED (not "
            "overturned) by a nighttime LST analysis (MOD11A1 LST_Night) or an "
            "intra-urban air-temperature comparison showing a positive urban signal."
        ),
        generation_method="aether_causal.heat_factors v1 (deterministic templating)",
    )

    # ---------------- ranking + non-discrimination headline ----------------
    contributors = sorted([f1, f2, f3], key=lambda f: -f.score)
    ranked = [*contributors, f4, f5]
    factors = [f.model_copy(update={"rank": i + 1}) for i, f in enumerate(ranked)]

    top_gap = abs(contributors[0].score - contributors[1].score)
    undiscriminated = top_gap < DISCRIMINATION_RESOLUTION
    top_names = f"{contributors[0].id} and {contributors[1].id}"
    if undiscriminated:
        headline = (
            f"THE TOP FACTORS CANNOT BE DISCRIMINATED: {top_names} "
            f"(synoptic ridge; antecedent soil dryness) score within "
            f"{top_gap:.2f} of each other — inside the "
            f"{DISCRIMINATION_RESOLUTION} resolving power of these co-varying, "
            "heuristic diagnostics. Ridges dry the soil and dry soils amplify "
            "ridges; with reanalysis diagnostics alone the engine can establish "
            "that BOTH were present, rare, and persistent, but cannot apportion "
            "the temperature anomaly between them. That non-discrimination is the "
            "finding, not a failure. Advection (F3) ranks below both; humidity "
            "(F4) frames severity only; the urban-fabric prior is argued AGAINST "
            "by the measured negative daytime surface UHI (F5)."
        )
    else:
        headline = (
            f"{contributors[0].id} ({contributors[0].factor_name.split(' /')[0]}) "
            f"leads {contributors[1].id} by {top_gap:.2f} "
            f"(>{DISCRIMINATION_RESOLUTION}) under the documented heuristic — a "
            "ranking, not an established apportionment. The expected "
            "ridge-vs-dry-soil entanglement did NOT materialize for this event "
            "because the diagnostics argue against several popular priors: "
            f"antecedent soil moisture was near climatology (dryness rank "
            f"{ant_dry:.0%} — the pre-dried-land narrative is unsupported), "
            f"low-level flow was essentially climatological (anomaly "
            f"{winds['anomaly_magnitude_ms']} m/s), airmass humidity was "
            f"near-normal (rank {dry_pct:.0%} dry), and the urban-fabric prior is "
            f"argued AGAINST by the measured negative daytime surface UHI "
            f"({uhi['window_mean_uhi_k']:+.2f} K). What remains, by these "
            "diagnostics, is a rare and persistent synoptic ridge "
            f"(+{z['anomaly_m']} m, above all 30 climatology windows, "
            f"{z['days_above_pooled_p90']}/{z['n_window_days']} days above the "
            "pooled p90) over a region whose in-window drying followed the heat."
        )

    return FactorHypothesisSet(
        event_id=event_id,
        phenomenon="heat_wave",
        generated_method="aether_causal.heat_factors v1 — deterministic, no LLM",
        headline_finding=headline,
        scoring_disclaimer=(
            "Scores are documented heuristics over computed diagnostics — weighted "
            "presence/rarity/persistence indices, NOT calibrated probabilities and "
            "NOT contribution fractions. Use the tiers and the headline, not the "
            "decimals."
        ),
        confidence_cap=(
            f"Warming-contributor tiers are capped at {FACTOR_CEILING.value}: "
            "diagnostics establish presence and rarity of co-varying factors but "
            "cannot causally separate them without counterfactual experiments "
            "(out of scope). HIGH is reserved and unearned."
        ),
        attribution_boundary=(
            "This engine ranks PHYSICAL CONTRIBUTING FACTORS with computed "
            "diagnostics. It does NOT perform probabilistic extreme-event "
            "attribution (anthropogenic influence). The published attribution "
            "result below is cited external evidence — never computed here, never "
            "blended into factor scores."
        ),
        event_summary={
            "event": "NW/central India heat wave, canonical window 2022-04-02..11",
            "air_anomaly": "window-mean regional Tmax anomaly +5.10 K (VALIDATED, Stage B)",
            "peak": "46.68 degC (2022-04-10; VALIDATED vs stations, Stage B)",
        },
        global_assumptions=[
            "All reanalysis diagnostics are ERA5 (one model family): a coherent but "
            "non-independent evidence base; cross-product replication of diagnostics "
            "is a future-work item.",
            "06:00 UTC (11:30 IST) sampling for every factor variable (consistent "
            "across factors and climatologies).",
            "Climatology period 1991-2020 with the Stage B baseline caveat (the "
            "warming trend inside the normals period was measured at 0.40 K "
            "half-spread for Tmax anomalies).",
        ],
        factors=factors,
        external_published_attribution=[
            EvidenceItem(
                kind="external_published_attribution",
                statement=(
                    "Zachariah et al. (2023): human-induced climate change made the "
                    "March-April 2022 India-Pakistan heatwave about 30 times more "
                    "likely and ~1 degC hotter than in a preindustrial climate "
                    "(~1-in-100-year event in the 2022 climate). CITED EXTERNAL "
                    "RESULT — not computed by Aether, not part of any factor score."
                ),
                source=SourceRef(
                    dataset=(
                        "Zachariah, M., et al. (2023). Environmental Research: "
                        "Climate, 2(4), 045005. doi:10.1088/2752-5295/acf4b6"
                    ),
                    locator="https://doi.org/10.1088/2752-5295/acf4b6",
                ),
            )
        ],
        provenance=dict(diag["provenance"]),
    )


def render_factors_markdown(hs: FactorHypothesisSet) -> str:
    """Human-readable rendering of the factor set (deterministic)."""
    lines = [
        f"# Factor hypotheses — {hs.event_id}",
        "",
        f"**Headline.** {hs.headline_finding}",
        "",
        f"**Attribution boundary.** {hs.attribution_boundary}",
        "",
        f"**Scoring disclaimer.** {hs.scoring_disclaimer}",
        "",
        f"**Confidence cap.** {hs.confidence_cap}",
        "",
    ]
    for f in hs.factors:
        lines += [
            f"## {f.id} (rank {f.rank}) — {f.factor_name}",
            "",
            f"*Role:* {f.role.value} · *Tier:* **{f.confidence_tier.value}** · "
            f"*Score:* {f.score:.2f} (heuristic)",
            "",
            f.claim,
            "",
            "**Diagnostics (every claim binds to these):**",
            *(
                f"- `{d.name}` = {d.value} {d.unit} — {d.definition} "
                f"(source: {d.source.locator})"
                for d in f.diagnostics
            ),
            "",
            "**Assumptions:**",
            *(f"- {a}" for a in f.assumptions),
            "",
            "**Counter-considerations:**",
            *(f"- {c}" for c in f.counter_considerations),
            "",
            f"**Falsification:** {f.falsification}",
            "",
        ]
    lines += ["## External published attribution (cited, never scored)", ""]
    for e in hs.external_published_attribution:
        lines += [f"- {e.statement}", f"  - Source: {e.source.dataset}", ""]
    return "\n".join(lines)
