"use client";

// The right-hand inspector. Pure presentation of one EventDetail — every number
// is read from the prop (sourced by the API from committed Stage A/B files).
import SourceAttribution from "./SourceAttribution";
import type { EventDetail, HypothesisSet } from "@/lib/types";

type QCal = "ours" | "nasa";

const f1 = (n: number) => n.toFixed(1);
const f2 = (n: number) => n.toFixed(2);
// Headline rate: sub-1 t/hr shows 2 decimals (0.85, not 0.9); else 1.
const fmtRate = (n: number) => (Math.abs(n) < 1 ? n.toFixed(2) : n.toFixed(1));

export default function Inspector({
  detail,
  hypotheses,
  qcal,
  onQcal,
  onResizeStart,
}: {
  detail: EventDetail;
  hypotheses: HypothesisSet | null;
  qcal: QCal;
  onQcal: (c: QCal) => void;
  onResizeStart: (e: React.PointerEvent) => void;
}) {
  const chipClass = ["type", "body", "sensor"];

  return (
    <div className="inspector">
      {/* drag the left edge to resize the panel; the plume stage reflows live */}
      <div className="panel-resize" onPointerDown={onResizeStart} title="Drag to resize" />
      <div className="insp-scroll">
        <div className="evt-head">
          <div className="evt-toprow">
            <div className="evt-name">{detail.short_name}</div>
            {/* document code = the real event_id, nothing invented */}
            <div className="evt-code">{detail.event_id}</div>
          </div>
          <div className="evt-sub">{detail.location_label}</div>
          <div className="evt-chips">
            {detail.chips.map((c, i) => (
              <span key={c} className={`chip ${chipClass[i] ?? "sensor"}`}>
                {c}
              </span>
            ))}
            {detail.validation_tier && (
              <span
                className={`tier-badge tier-${detail.validation_tier.toLowerCase().replace(/[^a-z]/g, "-")}`}
                title="Validation tier"
              >
                {detail.validation_tier}
              </span>
            )}
            {detail.status === "pending" && <span className="pending-badge">Pending</span>}
          </div>
          {/* First-class tier explainer: what this tier means for THIS event + limits. */}
          {detail.tier_explainer && <p className="tier-explainer">{detail.tier_explainer}</p>}
        </div>

        {detail.status === "pending"
          ? renderPending(detail)
          : renderActive(detail, qcal, onQcal)}

        {/* Source attribution renders the committed Sprint 4 artifact verbatim;
            absent for pending events (the API returns no artifact). */}
        {hypotheses && <SourceAttribution data={hypotheses} />}

        {detail.references.length > 0 && (
          <div className="panel">
            <div className="panel-h">
              <span className="tag">Provenance · References</span>
              <span className="line" />
            </div>
            {detail.provenance?.localization && (
              <div className="ref prov-localization">
                <b>Source localization:</b> {detail.provenance.localization}
              </div>
            )}
            {detail.references.map((r, i) => (
              <div className="ref" key={i}>
                {r.citation}
                {r.doi && (
                  <a className="doi" href={`https://doi.org/${r.doi}`} target="_blank" rel="noreferrer">
                    doi:{r.doi}
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function renderPending(detail: EventDetail) {
  return (
    <div className="caveat">
      <div className="ch">Pending · No Quantification</div>
      <p className="pending-note">{detail.pending_reason}</p>
    </div>
  );
}

function renderActive(detail: EventDetail, qcal: QCal, onQcal: (c: QCal) => void) {
  const q = detail.quantification!;
  const geom = detail.geometry!;
  const atmos = detail.atmosphere!;
  const val = detail.validation!;
  const scope = detail.scope_caveat!;
  const cal = qcal === "ours" ? q.ours_cal : q.nasa_cal;

  return (
    <>
      <div className="panel">
        <div className="panel-h">
          <span className="tag">Emission Rate · IME</span>
          <span className="line" />
        </div>
        <div className="q-cal">
          <button className={qcal === "ours" ? "on" : ""} onClick={() => onQcal("ours")}>
            OURS-CAL
          </button>
          <button className={qcal === "nasa" ? "on" : ""} onClick={() => onQcal("nasa")}>
            NASA-CAL
          </button>
        </div>
        <div className="q-big">
          <span className="num">{fmtRate(cal.value_t_hr)}</span>
          <span className="unit">t CH₄ / hr</span>
        </div>
        <div className="q-range">
          range{" "}
          <b>
            {f1(cal.range_low_t_hr)} – {f1(cal.range_high_t_hr)}
          </b>{" "}
          t/hr · 1σ ±{f1(cal.sigma_fractional * 100)}%
        </div>
        <div className="q-note">{cal.note}</div>
      </div>

      <div className="panel">
        <div className="panel-h">
          <span className="tag">Uncertainty Budget</span>
          <span className="line" />
        </div>
        {detail.uncertainty_budget.map((t) => (
          <div className={`ubar ${t.kind === "systematic" ? "sys" : ""}`} key={t.key}>
            <div className="ubar-top">
              <span className="k">{t.label}</span>
              <span className="v">{t.display}</span>
            </div>
            <div className="ubar-track">
              <div className="ubar-fill" style={{ width: `${Math.round(t.bar_fraction * 100)}%` }} />
            </div>
          </div>
        ))}
      </div>

      <div className="caveat">
        <div className="ch">Scope · Read Before Citing</div>
        <p>{scope.text}</p>
      </div>

      <div className="panel">
        <div className="panel-h">
          <span className="tag">Stage A Validation</span>
          <span className="line" />
        </div>
        {/* spec-sheet meter (replaces the v1 radial gauge): the same value,
            plus every other validation number the API already serves */}
        <div className="meter-head">
          <span className="meter-num">{f2(val.pearson_in_bbox)}</span>
          <span className="meter-cap">Pearson r · in-bbox</span>
        </div>
        <div className="meter-track">
          <div
            className="meter-fill"
            style={{ width: `${Math.round(Math.max(0, Math.min(1, val.pearson_in_bbox)) * 100)}%` }}
          />
        </div>
        <Drow k="Reference product" v={val.reference_product} u="" />
        <Drow k="Pearson (full scene)" v={f2(val.pearson_full_scene)} u="" />
        <Drow k="Pixels in bbox" v={String(val.n_pixels_bbox)} u="px" />
        {val.integrated_mass_ratio !== null && (
          <Drow k="Integrated mass (ours/NASA)" v={f2(val.integrated_mass_ratio)} u="×" />
        )}
        {val.pixel_pearson !== null && (
          <Drow k="Plume-pixel Pearson" v={f2(val.pixel_pearson)} u="" />
        )}
        <p className="vtext">{val.note}</p>
      </div>

      <div className="panel">
        <div className="panel-h">
          <span className="tag">Plume Geometry</span>
          <span className="line" />
        </div>
        <Drow k="Integrated mass (IME)" v={f2(geom.ime_t)} u="t" />
        <Drow k="Mask area" v={f1(geom.area_km2)} u="km²" />
        <Drow k="Length L = √A" v={f2(geom.length_km)} u="km" />
      </div>

      <div className="panel">
        <div className="panel-h">
          <span className="tag">Atmospheric State</span>
          <span className="line" />
        </div>
        <Drow k="ERA5 |U₁₀|" v={f2(atmos.u10_speed_ms)} u="m/s" />
        <Drow k="U_eff (Varon Eq 12)" v={f2(atmos.u_eff_ms)} u="m/s" />
      </div>

      {detail.brief && (
        <div className="panel brief">
          <div className="panel-h">
            <span className="tag">Generated Brief</span>
            <span className="line" />
          </div>
          <p>{detail.brief}</p>
        </div>
      )}
    </>
  );
}

function Drow({ k, v, u }: { k: string; v: string; u: string }) {
  return (
    <div className="drow">
      <span className="k">{k}</span>
      <span className="v">
        {v}
        <span className="u">{u}</span>
      </span>
    </div>
  );
}
