# Stage B — Permian/Carlsbad 2022-08-26 — per-granule v2 HITRAN k (NASA-footprint-anchored)

**Validation tier: CROSS-CHECKED** (NASA L2B CH4ENH exists → spatial Pearson + footprint cross-check; NO peer-reviewed per-source flux). 18.3 t/hr is press-release CONTEXT only — never a target.

## Headline
- **Q (ours, over NASA's published complex-000524 footprint, L2B>200)**: 0.85 t/hr
- **Cross-check — NASA's OWN L2B over the same footprint + method**: 0.88 t/hr (ours/NASA IME = 0.96×)
- **Q range with all uncertainty**: [0.57, 1.15] t/hr
- **Retrieval**: independent per-granule v2 saturation-aware HITRAN2020/HAPI k (no NASA target exists for this granule → no k-shape cross-check).
- **MF-amplitude transfer test**: Goturdepe measured +1.46× (ours HIGH); here 0.96× (ours LOW) — the systematic does NOT transfer.

## Self-segmentation (generality finding)
- Our own Varon self-segmentation isolated the plume: **False** (171 px, NASA-mean over its CC -36 ppm·m). The plume is weak vs scene clutter, so self-segmentation grabs a confuser — hence the NASA-footprint anchor.

## Geometry & surface state
- Footprint 123 px, area 0.38 km², L=√A 0.62 km
- Centroid: (32.3539 N, -104.0821 E)
- Surface state (ERA5): p=90897 Pa, T=303.5 K, n_air=36.02 mol/m³

## Wind & U_eff regime
- |U₁₀| = 3.58 m/s, U_eff = 1.875 m/s, σ_U10 = 1.69 m/s
- Varon regime [2, 8] m/s: in-range=True; margin to low=1.58 m/s, to high=4.42 m/s; boundary-proximate=False
- Source-vs-centroid ΔQ = 0.0%

## Uncertainty budget (from scratch)
| Term | Fractional |
|---|---|
| Wind α₁ | 0.068 |
| Wind U₁₀ | 0.252 |
| Wind combined | 0.261 |
| Mask (footprint-threshold) sensitivity (half-spread) | 0.245 |
| **Symmetric combined** | **0.358** |
| MF amplitude (measured this scene, one-sided) | 0.96× |
| MF amplitude (carried Goturdepe prior, transfer test) | 1.46× |

### Footprint-threshold sensitivity sweep
| NASA L2B threshold (ppm·m) | mask px | Q ours (t/hr) |
|---|---|---|
| 100 | 182 | 0.798 |
| 200 | 123 | 0.851 |
| 500 | 21 | 0.434 |
