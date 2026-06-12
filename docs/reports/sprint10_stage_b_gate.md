# Sprint 10 — Stage B gate ruling (recorded verbatim from review, 2026-06-12)

Ruling on `docs/reports/sprint10_stage_b_report.md` (Stage B head `fc3db84`): **APPROVED with one addition.**

## Accepted

- **response_model removal on the three streamed routes ACCEPTED** — startup validation + suite
  guards + byte-identity is the stronger contract.
- **Attribution split ACCEPTED** — statusbar carries "Powered by Esri" + the full ERA5 CC-BY line;
  the Esri data-source credit renders on Cesium's credit display.
- **F1 split outcome accepted.**
- **.npz leak find-and-fix commended**, but the `.dockerignore` denylist is **insufficient as a
  durable invariant**.

## The addition (required before any deploy)

**Image-inventory guard:** extend the live-container guard set (or add a build-verification step)
asserting that **EVERY file under `/app/data` in the built image appears in `git ls-files` for the
corresponding trees at the build SHA** — a positive subset check, not a pattern denylist. The
`.dockerignore` stays as belt; this guard is the suspenders. It must **fail red on a planted
gitignored file**. Run it against a rebuilt image and include the result in the Stage C report.

## DNS facts for the runbook (verified by the reviewer via direct NS/A/CNAME lookups, 2026-06-12)

- `arkaneworks.co` DNS is hosted on **Namecheap default nameservers** (`dns1`/`dns2.registrar-servers.com`).
- Apex = **GitHub Pages A records** (185.199.108–111.153).
- `www` = CNAME `animeshrajvanshi.github.io`.
- `aether.arkaneworks.co` is currently **NXDOMAIN (free)**.

The [Human] DNS step is therefore concrete: Namecheap → Domain List → `arkaneworks.co` →
Advanced DNS → Add New Record → **CNAME**, Host `aether`, Value = **the exact target shown in
Vercel's domain-add dialog** (do NOT hardcode `cname.vercel-dns.com` as authoritative; the
dashboard value wins). Existing apex/`www` records untouched.

## Effect

Stage C is unblocked once the image-inventory guard exists and is green on a rebuilt image (red
proof included). Stage C runs per the brief + Gate A amendment: fly.toml always-on
(`auto_stop_machines = "off"`), smallest shared-cpu 256 MB machine, region nearest Los Angeles,
single worker; every [Human] step enumerated and PAUSED on; STOP at the Stage C gate with the live
URL, the runbook as executed, observed cold-start/first-paint numbers, and the hosted shot list.
