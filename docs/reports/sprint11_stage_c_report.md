# Sprint 11 — Stage C report: the arkaneworks case-study page (ape.html)

**Stage:** C (arkaneworks WEBSITE repo). **Status:** built + committed locally, **deploy proposed,
NOT pushed** (the one push this stage needs is approval-gated). Aether-repo commits stay unpushed.
**Website repo:** `AnimeshRajvanshi/arkaneworks`, local commit `fa84f0e` on `main` (1 ahead of origin).

## Website preservation — the hard gate criterion (PASSED)

Exactly one file changed, and the shared assets are byte-identical:

```
$ git diff --stat            # (HEAD~1..HEAD)
 ape.html | 143 ++++++++++++++++++++++++++++++++++++++++++++++++--
 1 file changed, 135 insertions(+), 8 deletions(-)

$ git status --short
 (clean — only ape.html was committed)
```

- **`styles.css` byte-identical** — `shasum` before and after both `4639bb5a65738375fde7b08e6bf958ed3e12c02e`.
- **`script.js` byte-identical** — both `258e841740ffdd0645bac6f8b6a41dfa3f7ca125`.
- **Untouched:** the shared nav dropdown, `lunar.html` (the unrelated Moon-Presence program), `cubesat.html`,
  and every other page. `git diff --name-only` = `ape.html`.
- **No new shared CSS.** Everything the page needs is either an existing class (reused from
  `cubesat.html`'s scaffold) or a small `<style>` block **scoped inside `ape.html`** that composes the
  shared design tokens (`--ink`, `--line`, `--panel`, `--font-mono`, …). Nothing was added to the
  shared stylesheet.
- **No dashboard colour entered the website.** The page CSS uses only the monochrome site tokens; the
  only `amber/cyan` string in the file is the comment documenting that constraint. The favicon data-URI
  uses `#0d0d0d`/`#e7e7e2` — the site's own monochrome, identical to every other page.

## Design fidelity — a sibling of the other project pages

`ape.html` is templated on `cubesat.html` (itself a hyperspectral remote-sensing page): the same
`menu-bar` + dropdown nav markup verbatim, the same `project-hero` → `spec-row` → `content-blocks`
(`panel-head` + `.idx`) → `custom-list` references → `pager` scaffold, the same `reveal` /
`scroll-progress` / `scroll-arrow` behaviour hooks (so `script.js` drives it identically), the same
monochrome industrial system (Space Grotesk + IBM Plex Mono, `#0d0d0d`/`#e7e7e2`, drafting grid,
notched corners). The `doc-code` reads `AW–P02 · Active Program` and the crumbs read
`Present / P-02 / Active`, matching its real slot. HTML validates (no unclosed/stray tags).

## Content — from the approved ledger + the Stage B snippet

Structure for a Carbon Mapper hiring manager: **honest hook → problem → what was built → the rigor →
the numbers → see it live → lineage → where this is headed → references.**

- **First sentence is the honest hook** — "a working Earth-observation dashboard that detects and
  quantifies methane super-emitter plumes and reconstructs heat-wave events — and every number it shows
  traces back to a committed data artifact …" — reality before the grand name. The name "Aether
  Planetary Engine (A.P.E.)" is kept (it is the project's name); the planetary-engine / lunar / SDA /
  exoplanet / multi-body cosmology **does not appear anywhere** (cardinal rule 2, per the Stage A gate
  ruling).
- **The rigor leads with the failures** — pre-registration; C1/C2 VALIDATED vs the **C3/C4 FAILED**
  finding; the methane flux **CROSS-CHECKED, not VALIDATED**; the **+1.46×** reproduced-and-uncorrected
  systematic; the **negative UHI** counter-evidence; the deployed-integrity guard.
- **The single labeled "Where this is headed"** horizon is **Aether's own roadmap** — more events, more
  sensors in the existing methane/heat lanes (TROPOMI, more thermal), and the repository's logged
  deferred items (the residual +1.46× physics; the automated visual-fidelity check). **Not** the
  planetary/lunar/SDA cosmology.
- **F5 boundary preserved** — Carbon Mapper complementary/inspired-by, shared JPL spectrometer
  *heritage* not pipeline equivalence, not affiliated/endorsed.
- **Case study vs live demo kept explicit** — "arkaneworks.co/ape is this write-up,
  aether.arkaneworks.co is the running dashboard."

## Figure provenance (no retyping)

Every figure on the page is a display string from the committed source-of-truth snippet
`docs/key_results.json`, stamped on the page as **"as of aether `91620d5`"** (the snippet's recorded
data SHA). Verified present and matching: `23.4 t/hr`, `16.0 t/hr`, `±12.8%`, `r = 0.731`, `0.993`,
`1.46×`, `0.85 t/hr`, `0.96×`, `0.137`, `46.68 °C`, `+5.67 K`, `26 d / 889,700 km²`, `−0.77 K`. (The
"26 d / 889,700 km²" cell pairs the C3 and C4 figures; both numbers are verbatim from the snippet, the
slash is layout only.)

## Screenshots — what I can and cannot produce

Per the brief, screenshots are intended in two senses; here is the honest accounting:

1. **Dashboard screenshots embedded *in* the page** — **not embedded this stage, by design.** Embedding
   PNGs would add asset files and break the "exactly one file changes / `git diff --stat` = `ape.html`
   only" hard gate. Instead the page drives the reader to the live demo with a labelled shot-list of
   exactly the views the brief named (three-event globe, per-quantity tier table, two-lanes heat block,
   factor-attribution panel with counter-evidence + external-attribution boundary). If embedded
   screenshots are wanted, that is a **deliberate follow-up asset commit** (it will expand the diff
   beyond `ape.html`) — flagged for your call at the gate, not done unilaterally.
2. **A browser screenshot of the rendered `ape.html`** — **I cannot capture one** (no headless browser
   is available to the agent — the project's standing limitation, noted across prior sprints). I have
   instead proven fidelity structurally: only `ape.html` changed, shared CSS/JS byte-identical, the page
   reuses `cubesat.html`'s exact scaffold and classes, so it renders in the site chrome identically to
   its siblings. **Visual confirmation is yours** — open `ape.html` locally, or eyeball the deployed
   page once the push below is approved.

## Deploy — PROPOSED, approval-gated (not pushed)

The website deploys via its existing GitHub Pages mechanism (legacy build, source `main` path `/`). The
one push this stage needs:

```
# in the arkaneworks repo, on your approval:
git -C <arkaneworks> push origin main      # triggers the Pages rebuild → https://arkaneworks.co/ape
```

I have **not** pushed. On approval I (or you) push the single commit `fa84f0e`; Pages rebuilds and
`arkaneworks.co/ape` updates. Apex / `www` / the `aether.` subdomain config are untouched.

## Flags for the gate

- **Outbound links to the repo / README / write-up require two human actions to resolve** at Stage D:
  (a) the aether **Stage A/B commits must be pushed** to `origin/main` (they are held unpushed —
  `main` is ahead of origin), and (b) the **aether repo must be public** (README still says "Currently
  private"). The live-demo link (`aether.arkaneworks.co`) already resolves. All links are to be
  **verified live at Stage D** per the brief — schedule that read *after* the aether push + visibility
  change.
- **Embedded dashboard screenshots** deferred per the one-file gate (item 1 above) — your call whether
  to add them as a follow-up asset commit.

**STOP at the Stage C gate.** Next (Stage D): the integrated read-through as the target reader
(case study → live demo → README → write-up), cross-deliverable figure consistency, no overclaim,
caveats present, link integrity, site integrity — after the proposed pushes are approved.
