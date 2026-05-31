# Task: Sprint 1, Item 5 — EMIT proof-of-life

**Owner:** Claude Code
**Reviewer:** chat Claude (architecture/science) + human (runs it, has NASA account)
**This is the Sprint 1 gate.** When it passes, Sprint 1 is complete.

## Goal

Implement the command `aether reproduce <event_id>` such that, given a benchmark event that was observed by EMIT, it:

1. Resolves which EMIT granule(s) cover the event's location and date.
2. Downloads the relevant EMIT L2B methane data (with the user's NASA Earthdata credentials).
3. Caches it locally in a cloud-optimized format (Zarr) under `.aether_cache/`.
4. Loads it, orthorectifies if needed, and renders the methane enhancement layer as a static map (PNG) with the plume clearly visible.
5. Saves the PNG to an output path and prints where it went.

The deliverable that proves success is a **PNG showing a real methane plume from real EMIT data**, reproduced on the human's machine.

## Prerequisite the human must do (not you)

The human must create a free **NASA Earthdata Login** account at https://urs.earthdata.nasa.gov and, for EMIT data on the LP DAAC, may need to authorize the relevant application. Do **not** attempt to create the account or enter credentials yourself. Use `earthaccess.login()`, which prompts interactively and can persist to `~/.netrc`. The human runs that step.

## Approach — verify before you build

EMIT product specifics change. **Before hardcoding anything**, read the authoritative sources and confirm current details:

- NASA's **EMIT-Data-Resources** GitHub repository (the canonical how-to for working with EMIT data, including the orthorectification / GLT workflow and example notebooks).
- The **LP DAAC** product pages for the EMIT L2B methane products.
- Confirm: the exact product short-name(s) and current version, the variable name(s) for methane enhancement, the units, and whether the L2B methane product is delivered orthorectified or in sensor geometry requiring a GLT (Geometric Lookup Table).

State what you found and cite the source in your summary and in code comments. If you cannot verify a detail, leave a clearly-marked TODO rather than guessing.

## Known gotchas (do not skip these)

- **EMIT geolocation is not trivial.** EMIT L1B/L2A data ships in sensor geometry and requires orthorectification via a GLT. Determine whether the L2B methane enhancement product needs the same treatment. The NASA EMIT-Data-Resources repo has the canonical `emit_xarray` / orthorectification helpers — use or adapt them rather than reinventing.
- **EMIT is on the ISS**, not a sun-synchronous orbit. Coverage is opportunistic and gappy. Not every location/date has an EMIT granule. Pick an event you can confirm has coverage.
- **Downloads are large** (hundreds of MB per granule). Cache aggressively; never re-download what's cached. Show a progress indicator.
- **GDAL-backed deps** (rasterio/rioxarray) can be finicky. Confirm they install cleanly on Python 3.12 via uv wheels before building on them.

## Finding a real EMIT-observable plume

You need a benchmark event that EMIT actually saw. Two viable paths:

- **Path A (preferred):** NASA publishes EMIT methane plume locations directly. Use the EMIT methane plume product / NASA's documented example plumes to get a confirmed plume with a known granule, lat/lon, and date.
- **Path B:** Carbon Mapper's public portal (https://carbonmapper.org/data) hosts EMIT-attributed plumes with coordinates and dates; the human can register and pull one, then you find the matching EMIT granule on Earthdata.

Once you have a confirmed plume, **add it as a new benchmark event** in `eval/benchmark/` following the existing `aliso_canyon_2015.yaml` schema — with real references. This becomes the first EMIT-observable benchmark event.

## Deliverables

1. **`packages/data_spine`** — a real package (register it in the workspace) with an `emit` module exposing functions to: authenticate, search granules by lat/lon/date, download with caching, load as xarray, orthorectify, extract the methane enhancement layer.
2. **A `reproduce` command** — either as a new `aether` CLI (a small top-level package) or wired into the existing structure. `aether reproduce <event_id>` does the full flow above. Discuss with the reviewer if the CLI home is unclear; default to a new `apps/cli` or `packages/cli` workspace member.
3. **A new EMIT-observable benchmark event** in `eval/benchmark/` with real references.
4. **Tests** — unit tests for the searchable/parsing logic (mock the network; do not hit NASA in CI). An integration test that actually downloads can exist but must be marked `@pytest.mark.integration` and skipped by default.
5. **The rendered PNG** — checked that it is NOT committed (it's data), but the human will eyeball it. Save to a sensible output path and print it.

## Definition of done (the gate)

- `uv run pytest` passes (unit tests; integration tests skipped by default).
- The human runs `aether reproduce <the_new_event_id>` on their Mac and gets a PNG showing a real methane plume from real EMIT data.
- The new benchmark event loads via `aether-eval show <event_id>`.
- You produce a summary: what product/variables you used, your source for those specifics, what you assumed, and anything you want the reviewer to scrutinize.

## Out of scope (do NOT do these now)

- No detection algorithm yet (that's Sprint 2). This task only ingests and renders EMIT's *existing* methane enhancement layer — it does not run our own plume detection.
- No quantification. No causal engine. No dashboard.
- Do not add data sources beyond EMIT for this task.
