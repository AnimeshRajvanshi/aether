# Sprint 6 — Operational HITRAN-k Migration — Gate Report

> Generated 2026-06-09 from a fresh re-run + full verification. This is the first
> gate report committed to a file (per the new "gate reports go to a committed
> file, not terminal-only" convention). Numbers below are read back from the
> regenerated committed artifacts, not transcribed from prior docs.

## Verdict

**Sprint 6 is complete.** The independent v2 saturation-aware HITRAN2020/HAPI `k`
is now the **operational** Goturdepe retrieval. The dashboard's displayed
quantification, uncertainty budget, provenance line, brief, scope caveat, and
source-attribution hypotheses are all re-derived from the v2 outputs. NASA's
per-granule target is used **only** as a spectral-shape cross-check (r = 0.993),
never as a pipeline input.

This was an outward-facing change (the headline moved 27.1 → 23.4 t/hr ours-cal);
it is committed and **held here for your review** before we declare Sprint 6 closed.

## Headline numbers (NASA-k → v2 HITRAN-k, all re-derived)

| quantity | NASA-`k` (was) | **v2 `k` (now)** | source |
|---|---:|---:|---|
| Q ours-cal | 27.09 t/hr | **23.40 t/hr** | `q_estimate.json:q_central_t_hr` |
| Q nasa-cal | 16.32 t/hr | **16.03 t/hr** | `q_estimate.json:q_central_nasa_calibrated_t_hr` |
| Q range (all uncertainty) | [14.22, 30.57] | **[13.97, 26.40] t/hr** | `q_low/high_t_hr` |
| MF amplitude systematic | 1.66× (hand-carried) | **1.46× (measured this run)** | `q_estimate.json:enhancement_bias_factor` |
| IME | 41.2 t | **35.7 t** | `ime_central_kg` |
| plume mask area | 192.6 km² | **193.8 km²** | `plume_cc_area_km2` |
| plume CC label | 1213 | **1143** | `plume_cc_label` |
| Pearson vs NASA L2B (bbox) | 0.749 | **0.731** | `stage_a_report.json:pearson_in_bbox` |
| Pearson vs NASA L2B (full) | 0.735 | **0.715** | `pearson_full_scene` |
| MF bands used | 49 | **49** | `bands_used` |
| scope: fraction of Thorpe cluster | ≈10–17% | **≈10–14%** | computed in API from Q |

## Step-by-step (against the 8-point brief)

1. **Re-ran the operational pipeline with v2 `k`.** New offline runner
   `scripts/run_migration_v2_operational.py` regenerates Stage A (MF → ortho →
   validation) and Stage B (segmentation → IME/Q → budget). Reproducible (exit 0,
   identical numbers across runs). NASA-`k` originals preserved alongside (see §
   "Filing decision").

2. **Re-propagated the uncertainty budget** (not transcribed):
   - **Wind terms unchanged by construction** — the v2 centroid and upwind source S
     fall in the same 0.25° ARCO-ERA5 grid cells as the NASA-`k` run, so the
     reanalysis returns identical winds. The runner **asserts** the grid-cell
     identity rather than re-fetching. Result: α₁ = 0.0763, U₁₀ = 0.1018,
     wind-combined = 0.1273 — bit-identical to NASA-`k`.
   - **Mask sensitivity shifted** with the new enhancement map: Q over
     p ∈ {0.01, 0.05, 0.10} = [22.70, 23.40, 23.26] t/hr (counts 50234 / 68814 /
     77180); spread 0.0391 → **0.0299**; half-spread 0.0195 → **0.0150**.
   - **MF-amplitude systematic** = independently measured ours/NASA mean ratio over
     the plume CC = **1.4603×** (not the hand-carried 1.66×).
   - Combined symmetric σ: 0.1287 → **0.1281**.

3. **Regenerated all derived artifacts** from the new outputs: dashboard
   `enhancement/nasa/diff.png`, `bounds.json` (colormap vmax 1156 → 974 ppm·m,
   P98 of the in-mask plume), `mask.geojson` (CC 1143); the API-templated brief;
   and `hypotheses.{json,md}` (the attribution prose now quotes Q ≈ 23 t/hr,
   regenerated from `q_central_t_hr`, not hand-edited). No-fabrication + byte-match
   guards pass.

4. **Scope-caveat fraction recomputed** (computed, not transcribed): the API derives
   it live as round(nasa_cal/ref%)–round(ours_cal/ref%) = round(9.83)–round(14.36)
   → **≈10–14%** of the Thorpe 163 ± 18 t/hr, 12-source cluster.

5. **Provenance line flipped, honestly.** `stage_a_report.target_spectrum_source`
   now names the independent HITRAN2020/HAPI saturation-aware generation (NASA
   target NOT used; shape cross-check r = 0.993, `k_nasa_target_used=false`). The
   OURS-CAL / NASA-CAL toggle notes and the brief were updated to the new meaning:
   OURS-CAL = the independent retrieval (~23.4); NASA-CAL = anchored to NASA L2B
   amplitude via the **measured** 1.46× ratio (~16.0). Forward scaling stays 1.0 —
   `k` is in 1/(ppm·m), never reverse-fit.

6. **New no-staleness guard suite** (`apps/api/tests/test_no_staleness.py`, 7 tests):
   parses the numbers embedded in derived-artifact **prose** (hypotheses claims /
   evidence / summary, the brief, the scope %, the API cal notes + budget) and
   asserts each equals its upstream committed source. This closes the gap the
   byte-match / regenerate==committed guards leave open — a value hardcoded in a
   generator reproduces identically and would slip through; parsing the rendered
   text catches it. **It found real staleness**: hardcoded "~27 t/hr" literals in
   the attribution rationales, now templated from `q_central_t_hr`. Negative
   control verified (reintroducing "~27 t/hr" fails the rate guard). The previously
   hardcoded `cc_label == 1213` and `~20 deg` bearing-gap test assertions were also
   converted to derive-from-source / self-consistency checks.

7. **Sprint 6 science doc updated** (`docs/science/sprint6_hitran_independence.md`
   §9 + §8 verdict): documents the migration; the 1.46× vs 1.66× residual is kept
   labelled a **hypothesis** (effective-layer background / flat-continuum
   approximation), explicitly **not** an established cause.

8. **This report** is the committed gate artifact.

## Verification (fresh run, 2026-06-09)

```
uv run pytest            -> 186 passed, 6 deselected, 2 warnings  (was 179; +7 no-staleness guards)
uv run aether-eval run   -> stub_pipeline, recall 0/3            (baseline; real MF still not wired into the harness)
apps/web: tsc --noEmit   -> clean
apps/web: next build     -> Compiled successfully, 5/5 static pages
uv run ruff check .      -> 72 errors, ALL pre-existing legacy debt (diagnostic scripts, ontology,
                            eval cli); every file touched in this migration lints clean per-file.
```

The 6 deselected pytest items are network-gated integration tests. The eval `0/3`
is unchanged and expected — the eval harness still runs a `stub_pipeline`; wiring
the real matched filter into the harness remains a separate open task and is **not**
part of this migration.

## Filing decision for review — "alongside, not over"

The brief said: *commit new stage outputs alongside (not over) the NASA-`k`
originals; do not delete history.* The committed scientific record is the JSON / MD
/ PNG (the large `.npz` ortho rasters are gitignored and regenerable).

I implemented this as: **the operational canonical filenames now carry the v2
result** (so the API, dashboard, attribution, and guard tests read and validate the
*served* artifacts), and **the NASA-`k` originals are preserved as committed
siblings**:

```
stage_a_outputs/<id>/stage_a_report.nasa_k.json
stage_b_outputs/<id>/q_estimate.nasa_k.json
stage_b_outputs/<id>/q_estimate_report.nasa_k.md
stage_b_outputs/<id>/wind_location_check.nasa_k.json
attribution_outputs/<id>/hypotheses.nasa_k.{json,md}
apps/api/aether_api/assets/<id>/_nasa_k/{enhancement,nasa,diff}.png, mask.geojson, bounds.json
```

Git history is intact, and the v1/v2/NASA comparison reports under
`stage_a_outputs/<id>/hitran_k/` are untouched. **If you'd prefer the inverse
filing** (NASA-`k` keeps the canonical names and v2 lives in `*.v2.*` with the
consumers/tests re-pointed), that's a rename — say the word and I'll switch it.

## What did NOT change / what remains open

- **Wind** — identical by construction (same ERA5 grid cells; asserted).
- **The 1.46× vs 1.66× residual** — still a hypothesis (effective-layer / flat
  continuum), unchanged by this migration; awaits the deferred physics refinements
  (layered background, H₂O/SZA LUT, per-pixel sensitivity, RFM cross-check).
- **Eval harness** still runs `stub_pipeline` (0/3); real MF not wired in.
- **Generalization** — all quantitative validation remains Goturdepe-only; Permian
  is still honest "pending".

## Screenshot evidence

The four requested panels — **headline Q, uncertainty budget, provenance line, and
an expanded H1** — are rendered data-exact (verbatim from the live API, the same
JSON the React Inspector binds to) in the committed companion file:

- **`docs/reports/sprint6_dashboard_panels.md`**

I did **not** fabricate browser PNGs. This environment has no browser-automation
driver installed (no Playwright/Puppeteer), and the CesiumJS globe needs a real
WebGL context that does not render headlessly — so an automated capture is not
available here. The panel-evidence file gives the exact reviewable content of all
four panels; for true PNG screenshots, run the app locally:

```
# terminal 1 — API
uv run uvicorn aether_api.main:app --port 8000
# terminal 2 — web
cd apps/web && pnpm dev      # http://localhost:3000
# click the GOTURDEPE–BARSAGELMEZ marker → the Inspector shows panels 1–3;
# scroll to Source Attribution and expand H1 for panel 4.
```

If you'd like, I can install Playwright and attempt a headless capture (best-effort
given the WebGL constraint) — say the word.
