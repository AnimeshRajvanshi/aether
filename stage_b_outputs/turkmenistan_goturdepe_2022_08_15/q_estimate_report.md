# Stage B — Q for plume CC 1213 (Goturdepe 2022-08-15 04:28:38 UTC)

## Headline
- **Q (central, ours-calibrated)**: 27.09 t/hr
- **Q (NASA-calibrated, IME / 1.66)**: 16.32 t/hr
- **Q range with all uncertainty**: [14.22, 30.57] t/hr
- **Scope**: ONE plume from a 12-source cluster. Thorpe 2023's 163 ± 18 t/hr is the *cluster total* and is NOT a same-scope reference. Compare as fraction-of-cluster, not equality.

## Geometry
- Plume CC label: 1213, 68382 pixels, area = 192.60 km², L = √A = 13.88 km
- Centroid: (39.3714 N, 53.6905 E)

## Wind
- ARCO-ERA5 nearest grid: (39.250 N, 53.750 E)
- 10 m wind components at overpass: u = -6.74 m/s, v = -1.62 m/s
- |U₁₀| = 6.93 m/s
- Hour distance to nearest ERA5 sample: 28.6 min
- σ_U10 (representativeness) = 1.79 m/s (Varon §7 baseline + hour-distance scaling)
- U_eff = α₁·ln(U₁₀) + α₂ = 2.537 m/s

## Mass
- n_air = 41.31 mol/m³ (p = 101325.0 Pa, T = 295.0 K)
- IME (central) = 41165.3 kg = 41.165 tonnes

## Uncertainty budget
| Term | Fractional |
|---|---|
| Wind α₁ (Varon Eq 12, ±0.1) | 0.076 |
| Wind U₁₀ (ERA5 representativeness) | 0.102 |
| Wind combined | 0.127 |
| Plume-mask sensitivity (half-spread over p∈(0.01, 0.05, 0.1)) | 0.020 |
| **Symmetric combined** | **0.129** |
| Enhancement-calibration bias (ours/NASA, integrated over CC) | 1.66× — asymmetric, one-sided |

### Mask-sensitivity sweep
| p | mask pixels | Q (t/hr) |
|---|---|---|
| 0.01 | 48583 | 26.028 |
| 0.05 | 68382 | 27.086 |
| 0.1 | 76154 | 26.779 |
