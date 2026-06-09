# Stage B — Q for plume CC 1143 (Goturdepe 2022-08-15 04:28:38 UTC) — v2 HITRAN k (operational)

## Headline
- **Q (central, ours-calibrated)**: 23.40 t/hr
- **Q (NASA-calibrated, IME / 1.46)**: 16.03 t/hr
- **Q range with all uncertainty**: [13.97, 26.40] t/hr
- **Retrieval**: independent v2 saturation-aware HITRAN2020/HAPI k (NASA per-granule target not used; shape cross-check r=0.993).
- **MF amplitude systematic**: independently measured 1.46× (ours/NASA over the plume CC) — reproduced from physics, not a NASA-convention artifact.
- **Scope**: ONE plume from a 12-source cluster. Thorpe 2023's 163 ± 18 t/hr is the *cluster total*, NOT a same-scope reference.

## Geometry
- Plume CC label 1143, 68814 px, area 193.82 km², L=√A 13.92 km
- Centroid: (39.3710 N, 53.6902 E)

## Wind (unchanged by construction — same ERA5 grid cell)
- |U₁₀| = 6.93 m/s, U_eff = 2.537 m/s, σ_U10 = 1.79 m/s

## Uncertainty budget (RE-PROPAGATED for v2)
| Term | Fractional |
|---|---|
| Wind α₁ | 0.076 |
| Wind U₁₀ | 0.102 |
| Wind combined | 0.127 |
| Plume-mask sensitivity (half-spread) | 0.015 |
| **Symmetric combined** | **0.128** |
| MF amplitude (measured, one-sided) | 1.46× |

### Mask-sensitivity sweep
| p | mask px | Q (t/hr) |
|---|---|---|
| 0.01 | 50234 | 22.705 |
| 0.05 | 68814 | 23.405 |
| 0.1 | 77180 | 23.255 |
