# Sprint 6 — HITRAN independence: validation & honesty document

**Goal:** replace NASA's per-granule methane target with a unit absorption
spectrum `k` we generate ourselves from HITRAN line-by-line spectroscopy, and
report — honestly — whether that independence reproduces the committed Goturdepe
result and at what (if any) calibration cost.

**Cardinal rule (held):** NASA's per-granule target file is a *validation
cross-check only*. Our `k` is computed from HITRAN line data + an atmospheric/path
model + EMIT's SRF, with **zero values read from NASA's file**. Enforced by guard
tests (`packages/detection/tests/test_hitran_k.py`): a dynamic guard records every
file opened during `generate_k` and asserts none is the NASA target; a static
guard asserts the source contains no NASA-target reference.

---

## 1. Recipe (Stage A) — how `k` is built

Spectroscopy: **HITRAN2020** (Gordon et al. 2022, JQSRT 277, 107949,
doi:10.1016/j.jqsrt.2021.107949) via **HAPI** (Kochanov et al. 2016, JQSRT 177,
15–30, doi:10.1016/j.jqsrt.2016.03.005). CH₄ (molecule 6, isotopologues
32/33/34/35), fetched over the **exact Sprint 2 window**
`MF_SPECTRAL_WINDOWS_NM` 2137–2493 nm → 4011–4680 cm⁻¹ (+60 cm⁻¹ margin); 67,715
lines cached + committed (`scripts/fetch_hitran_ch4.py`).

Steps (`aether_detection/hitran_k.py`), every approximation documented:
1. **Voigt cross-section** σ(ν) [cm²/molec] (HAPI, isotopologue-abundance
   weighted) at the near-surface enhancement layer's P, T (the scene's ERA5
   surface 101325 Pa / 295 K — our own input, never NASA's).
2. **Two-way air-mass factor** from the granule's own OBS geometry:
   AMF = sec(SZA) + sec(VZA) = sec(58.08°) + sec(8.26°) = **2.90**.
3. **Beer-Lambert linear unit absorption** (the EMIT/Thompson-2015 `k = d(ln L)/dc`
   definition): `k_hires(ν) = −AMF · σ(ν) · N_per_ppmm`, intrinsically negative.
4. **Gaussian-SRF convolution** to EMIT bands from the granule's own
   wavelength + FWHM arrays (σ = FWHM/2.355).

**Approximations:** effective surface layer for the enhancement; Beer-Lambert
linearization (no line-core saturation); plane-parallel two-way AMF. These are the
"well-justified effective-layer approximation" the task permits — and, as Stage B
shows, the **missing saturation is the dominant cost.**

### Stage A result (spectral shape, cross-check only)
Over the 49 MF-window bands: **Pearson r = 0.928, Spearman ρ = 0.964** vs NASA's
target. Our independent computation captures the same 2ν₃ absorption complex;
NASA is slightly deeper in saturated cores (consistent with MODTRAN saturation vs
our linear model). Overlay: `stage_a_outputs/.../hitran_k/hitran_k_vs_nasa.png`.

---

## 2. Absolute scaling — resolved FORWARD from the physics (not reverse-fit)

The matched filter solves `(x − μ) = α·(k ⊙ μ)`. Our `k` is in **1/(ppm·m of
vertical column)** and already carries the two-way AMF and the ppm·m unit chain:

```
k = −AMF · σ · N_per_ppmm
    AMF          = sec(58.08°) + sec(8.26°)              = 2.90      [two-way slant]
    N_per_ppmm   = 1e-6 · n_air(P,T) · 1 m  (→ molec/cm²) = 2.488e15  [excess CH4 column / ppm·m]
    σ            = HITRAN Voigt cross-section             [cm²/molec]
```

Because `k` is in 1/(ppm·m vertical), the raw MF `α` is **already in ppm·m
vertical** → the unit-conversion factor is **`ppm_scaling_factor = 1.0`** (NASA's
target encodes `k·Δc` and needs their published 1e5; ours does not). This 1.0 is
**derived from the unit chain — it was NOT chosen to make Q match 27.1 t/hr.**
(Consistency check, not an input: NASA's `k` ≈ 1e5·k_phys at weak bands, dropping
toward ~1e3 at saturated cores — exactly the saturation difference, and exactly
why the single 1e5 factor is a NASA-convention artifact, not physics.)

---

## 3. Stage B — end-to-end Goturdepe re-run with our `k` (algorithm unchanged)

`scripts/run_hitran_k_stage_b.py` swaps only the source of `k` and runs the
Sprint 2 MF → orthorectification → segmentation → IME unchanged.

**Pipeline faithfulness (control):** the same runner fed NASA's `k` (scale 1e5)
reproduces Pearson **full 0.7354 / bbox 0.7485** — bit-for-bit the committed
Sprint 2 values. So any change below is attributable to the `k` swap alone, not to
the pipeline.

| quantity | Sprint 2 (NASA k) | Ours (HITRAN k, forward scale 1.0) |
|---|---:|---:|
| Pearson vs NASA L2B (bbox) | 0.749 | **0.532** |
| Pearson vs NASA L2B (full) | 0.735 | 0.516 |
| plume CC pixels | 68 382 | 58 207 |
| IME | 41.2 t | 16.6 t |
| Q (ours-cal) | 27.09 t/hr | **11.87 t/hr** |
| amplitude vs NASA L2B over the CC | **1.66×** | **0.79×** |
| Q (anchored to NASA-L2B amplitude) | 16.32 t/hr | 15.04 t/hr |

Spatial diagnosis (bbox / strong-signal >200 ppm·m Pearson):

| | vs NASA L2B | vs Sprint 2 NASA-k map |
|---|---:|---:|
| our-k map | 0.532 / **0.044** | 0.694 / 0.516 |
| Sprint 2 NASA-k map | 0.749 / 0.521 | — |

Map comparison: `stage_a_outputs/.../hitran_k/stage_b_map_comparison.png`.

---

## 4. The headline question — calibration verdict (reported straight)

**Does our independent `k` change the +1.66× MF over-amplitude? Yes — it is not
preserved.** Under our own forward-scaled `k`, the retrieved enhancement is
**0.79× NASA L2B** (a mild *under*-amplitude), where Sprint 2's NASA-`k` run gave
1.66× (over-amplitude). So the 1.66× was a **NASA-`k`-convention × our-MF artifact,
not a universal property** — with a physically-scaled independent `k` it changes
sign of bias. The flux anchored to NASA-L2B amplitude is consistent either way:
**16.3 t/hr (Sprint 2) vs 15.0 t/hr (ours)** — within ~8%. The ours-cal Q drops
27→12 t/hr purely because the forward amplitude differs; this is re-derived
transparently, **not** tuned back to 27.1.

---

## 5. Independence verdict — achieved in spectroscopy, NOT yet in retrieval fidelity

- **Independence (spectroscopy): achieved.** `k` is genuinely ours; NASA's file is
  never read to build it (guard tests). Stage A shape validates at r = 0.93.
- **Retrieval fidelity: degraded.** Run end-to-end through the *unchanged* matched
  filter, our `k` does **not** preserve NASA's spatial agreement: bbox Pearson
  drops 0.75 → 0.53, and on the strong plume pixels the correlation with NASA L2B
  **collapses to ~0.04**. Our map also diverges from Sprint 2's NASA-`k` map
  (0.69 bbox / 0.52 strong).

**Diagnosis (before any fix; no patching toward NASA):** a 0.93 `k`-shape
correlation is a ~21° misalignment in the 49-band space. The matched filter is a
*projection* onto `s = k ⊙ μ`, and after whitening by the clutter covariance that
misalignment is amplified — most on the high-signal plume pixels. The physical
origin is the **missing line-core saturation** in our Beer-Lambert-linear `k`:
NASA's MODTRAN `k` is flattened in saturated cores, while ours retains full linear
contrast there, so the MF over-weights exactly the bands where the real signal is
saturated, injecting clutter and degrading the plume retrieval.

---

## 6. What we can and cannot claim

**CAN claim:** we generate a methane unit absorption spectrum **independently of
NASA** from HITRAN2020 + HAPI + an atmospheric/path model + EMIT's SRF; its
spectral **shape** matches NASA's per-granule target (r = 0.93); the absolute
scale is **forward-derived** from the ppm·m/AMF unit chain (`ppm_scaling = 1.0`),
not reverse-fit; and the NASA-L2B-anchored flux (~15 t/hr) is consistent with
Sprint 2 (~16 t/hr).

**CANNOT claim:** that the independent `k` is yet a drop-in operational replacement
— it does **not** reproduce NASA's retrieval fidelity (bbox Pearson 0.53, plume
correlation ~0). The 1.66× over-amplitude is **not** preserved (it becomes 0.79×).

**Provenance-line gate — NOT updated.** The dashboard provenance line still names
the NASA per-granule target, because the *committed operational retrieval* still
uses NASA's `k`: our independent `k` is a shape-validated prototype that does not
yet preserve fidelity. Per the gate ("do not change the UI claim unless the
validation backs it; if independence is partial, say exactly that"), we leave the
UI unchanged. Independence is achieved spectroscopically but is **not yet
retrieval-ready.**

**Principled next step (not this sprint, not NASA-tuning):** a saturation-aware
`k` — a layered column / finite-Δc Jacobian that includes line-core saturation
from the physics — to close the ~21° band-space gap with NASA's MODTRAN `k`
*through better physics, not by reading NASA's values.*

---

## 7. Reproducibility

```
uv run python scripts/fetch_hitran_ch4.py        # cache CH4 line list (committed)
uv run python scripts/run_hitran_k_stage_a.py    # k + shape validation (r=0.93)
uv run python scripts/run_hitran_k_stage_b.py    # end-to-end: Pearson, Q, calibration
uv run pytest packages/detection/tests/test_hitran_k.py   # incl. independence guards
```
