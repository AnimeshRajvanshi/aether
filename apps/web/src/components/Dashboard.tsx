"use client";

// Orchestrates the globe → fly-to → plume → inspector flow. Holds the view-phase
// state machine and the currently-selected event detail. CesiumGlobe is loaded
// client-only (it touches window/WebGL on import).
import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";
import type { FlyTarget } from "./CesiumGlobe";
import Inspector from "./Inspector";
import { fetchEvent, fetchEvents, fetchFactorHypotheses, fetchHypotheses } from "@/lib/api";
import type {
  EventDetail,
  EventSummary,
  FactorHypothesisSet,
  HypothesisSet,
  RetrievalLayer,
} from "@/lib/types";
import {
  clampPanelWidth,
  FLY_DURATION_S,
  FLY_EASING_CSS,
  PANEL_DEFAULT_W,
} from "@/lib/motion";

const CesiumGlobe = dynamic(() => import("./CesiumGlobe"), { ssr: false });

// "mounting" renders the populated panel off-screen (display:block, translated
// out) for one frame so the subsequent slide actually transitions instead of
// popping; the camera flight starts on that same next frame, keeping them synced.
type Phase = "globe" | "mounting" | "flying" | "detail" | "returning";
type QCal = "ours" | "nasa";

// Layer toggle labels — methane retrieval layers + heat field layers. A layer
// key missing here falls back to its raw key (never hidden).
const LAYER_LABELS: Record<string, string> = {
  enhancement: "Our Retrieval",
  nasa: "NASA L2B",
  diff: "Δ Diff",
  air_anomaly: "T2M Anomaly",
  air_baseline: "Baseline 1991-2020",
  lst_anomaly: "LST Anomaly",
};

/** "2022-08-15T04:28:38Z" -> "2022-08-15 04:28:38 UTC" (the granule overpass). */
function formatAcq(utc: string): string {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})/.exec(utc);
  return m ? `${m[1]} ${m[2]} UTC` : utc;
}

export default function Dashboard() {
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [body, setBody] = useState<"earth" | "moon" | "mars">("earth");
  const [phase, setPhase] = useState<Phase>("globe");
  const [detail, setDetail] = useState<EventDetail | null>(null);
  const [hypotheses, setHypotheses] = useState<HypothesisSet | null>(null);
  const [factors, setFactors] = useState<FactorHypothesisSet | null>(null);
  const [flyTarget, setFlyTarget] = useState<FlyTarget | null>(null);
  const [raster, setRaster] = useState<{
    eventId: string;
    bounds: { west: number; south: number; east: number; north: number };
    hasMask: boolean;
  } | null>(null);
  const [layer, setLayer] = useState<string>("enhancement");
  const [qcal, setQcal] = useState<QCal>("ours");
  const [error, setError] = useState<string | null>(null);
  const [panelWidth, setPanelWidth] = useState(PANEL_DEFAULT_W);

  useEffect(() => {
    fetchEvents().then(setEvents).catch((e) => setError(String(e)));
  }, []);

  // Select: fetch + populate the panel and drape the plume NOW, then start the
  // flight. The panel becomes visible at the same instant the camera starts
  // moving (see detailShown), so its fully-rendered content slides in over the
  // exact flyTo duration — one synchronized motion, no pop-in.
  const handleSelect = useCallback(async (ev: EventSummary) => {
    try {
      // Prefetch detail + both attribution artifacts together so the populated
      // panel (incl. attribution sections) is fully rendered as it slides in.
      const [d, hyp, fac] = await Promise.all([
        fetchEvent(ev.event_id),
        fetchHypotheses(ev.event_id),
        fetchFactorHypotheses(ev.event_id),
      ]);
      // Default layer = the event's own first layer (state isolation across
      // phenomenon types: "enhancement" was a CH4-shaped default).
      const bounds = d.heat ? d.heat.heat_raster.bounds : d.raster?.bounds;
      const layers = d.heat ? d.heat.heat_raster.layers : (d.raster?.layers ?? []);
      setLayer(layers[0] ?? "enhancement");
      setQcal("ours");
      setDetail(d);
      setHypotheses(hyp);
      setFactors(fac);
      if (bounds) setRaster({ eventId: d.event_id, bounds, hasMask: !d.heat });
      // Frame 1: mount the populated panel off-screen (display:block, slid out).
      setPhase("mounting");
      // Frame 2: begin the slide-in AND the camera flight together — synced.
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          setPhase("flying");
          setFlyTarget({ lon: ev.lon, lat: ev.lat, bounds });
        }),
      );
    } catch (e) {
      setError(String(e));
    }
  }, []);

  // Camera reached the plume — just mark arrival; the panel is already in.
  const onArrived = useCallback(() => setPhase("detail"), []);

  // Back: panel slides out as the camera pulls back (same shared duration).
  const onBack = useCallback(() => {
    setPhase("returning");
    setRaster(null);
    setFlyTarget(null);
  }, []);

  const onReturned = useCallback(() => {
    setPhase("globe");
    setDetail(null);
    setHypotheses(null);
    setFactors(null);
  }, []);

  // Drag the inspector's left edge to resize; clamped so neither side collapses.
  // Width is session state (in-memory) — intentionally not persisted to storage.
  const onResizeStart = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    const move = (ev: PointerEvent) =>
      setPanelWidth(clampPanelWidth(window.innerWidth - ev.clientX, window.innerWidth));
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      document.body.style.userSelect = "";
    };
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }, []);

  // mounted = overlay in the DOM (display:block); shown = slid in. They differ
  // by one frame on entry so the slide transitions, and the camera flight is
  // bound to the same `shown` toggle so panel + camera move as one (both ways).
  const detailMounted = phase !== "globe";
  const detailShown = phase === "flying" || phase === "detail";
  const activeEvents = events.filter((e) => e.status === "active");
  const pendingCount = events.filter((e) => e.status === "pending").length;
  // Acquisition timestamp of the SELECTED event's historical overpass (from
  // /api/events, which reads stage_a_report.json). With two live events a
  // global "first event" readout is ambiguous, so the chip only renders while
  // an event is selected. There is no live feed; nothing here is real-time.
  const selectedSummary = detail
    ? events.find((e) => e.event_id === detail.event_id) ?? null
    : null;
  const acquisition = selectedSummary?.acquisition_utc ?? null;

  return (
    <div className="app">
      <div className="topbar">
        <div className="wordmark">
          <div className="mark-top">AETHER</div>
          <div className="mark-sub">PLANETARY ENGINE · v0.3</div>
        </div>
        <div className="spacer" />
        <div className="top-status">
          <div className="si">
            <span className="lbl">Body</span>
            <span className="val">{body.toUpperCase()}</span>
          </div>
          {acquisition && (
            <div className="si">
              <span className="lbl">Acquired</span>
              <span className="val">{formatAcq(acquisition)}</span>
            </div>
          )}
        </div>
      </div>

      <div className="main">
        {/* Vertical data spine. Replaces the v1 icon rail: that rail was four
            non-functional nav buttons (Layers/Spectra/Catalog/Settings) — fake
            affordances. The spine carries only real state. */}
        <div className="spine">
          <div className="cross">+</div>
          <div className="spine-label">
            SUPER-EMITTER EVENT RECONSTRUCTION&ensp;//&ensp;
            <b>DETECTION · QUANTIFICATION · ATTRIBUTION · BRIEF</b>
          </div>
          <div className="cross">+</div>
        </div>

        <div
          className="stage"
          style={
            {
              "--fly-duration": `${FLY_DURATION_S}s`,
              "--fly-easing": FLY_EASING_CSS,
              "--panel-width": `${panelWidth}px`,
            } as CSSProperties
          }
        >
          <CesiumGlobe
            events={events}
            body={body}
            flyTarget={flyTarget}
            raster={raster}
            layer={layer}
            onSelect={handleSelect}
            onArrived={onArrived}
            onReturned={onReturned}
          />

          <div className={`bodysel ${phase !== "globe" ? "fade-out" : ""}`}>
            {(["earth", "moon", "mars"] as const).map((b) => (
              <button
                key={b}
                className={body === b ? "on" : ""}
                onClick={() => setBody(b)}
              >
                {b}
              </button>
            ))}
          </div>

          <div className={`readout ${phase !== "globe" ? "fade-out" : ""}`}>
            <div className="ro-row">
              <span className="ro-k">Signals</span>
              <span className="ro-v">
                {activeEvents.length} ACTIVE · {pendingCount} PENDING
              </span>
            </div>
            <div className="ro-row">
              <span className="ro-k">Quantities</span>
              {/* derived from the live catalog, not hardcoded to CH4 (Sprint 9) */}
              <span className="ro-v">
                {[
                  events.some((e) => e.phenomenon_type === "emission_event") && "CH₄ PLUME",
                  events.some((e) => e.phenomenon_type === "heat_wave") && "T2M / LST ANOM",
                ]
                  .filter(Boolean)
                  .join(" · ") || "—"}
              </span>
            </div>
            <div className="ro-row">
              <span className="ro-k">Products</span>
              <span className="ro-v">
                {[
                  events.some((e) => e.phenomenon_type === "emission_event") && "EMIT L2B",
                  events.some((e) => e.phenomenon_type === "heat_wave") &&
                    "ERA5 · MOD11A1 · ISD",
                ]
                  .filter(Boolean)
                  .join(" · ") || "—"}
              </span>
            </div>
          </div>

          <div className={`stage-hint ${phase !== "globe" ? "fade-out" : ""}`}>
            drag to orbit · scroll to zoom · <b>click a signal</b> to inspect
          </div>

          {body !== "earth" && (
            <div className="nodata-overlay">
              <div className="nodata-body">{body.toUpperCase()}</div>
              <div className="nodata-msg">NO DATA · EARTH MVP</div>
              <div className="nodata-sub">
                Planetary bodies beyond Earth are modelled in the ontology but not yet ingested.
              </div>
            </div>
          )}

          {error && (
            <div className="loading" style={{ color: "var(--alert)" }}>
              <div className="err-plate">API UNREACHABLE — start apps/api (uvicorn :8000)</div>
            </div>
          )}

          {/* ----- detail overlay (HUD + inspector); motion vars live on .stage ----- */}
          <div
            className={`detail ${detailMounted ? "mounted" : ""} ${detailShown ? "show" : ""}`}
          >
            <div className="plume-hud">
              <div className="bracket b1" />
              <div className="bracket b2" />
              <div className="bracket b3" />
              <div className="bracket b4" />
              <button className="back-btn" onClick={onBack}>
                ‹ BACK TO GLOBE
              </button>
              {detail?.geometry && (
                <div className="hud" style={{ top: 54, left: 16 }}>
                  <div className="coord-box">
                    <div className="ttl">Plume Origin</div>
                    <div className="coord-row">
                      <span>
                        LAT <b>{detail.geometry.centroid_lat.toFixed(3)}°N</b>
                      </span>
                      <span>
                        LON <b>{detail.geometry.centroid_lon.toFixed(3)}°E</b>
                      </span>
                    </div>
                  </div>
                </div>
              )}
              {detail?.heat && (
                <div className="hud" style={{ top: 54, left: 16 }}>
                  <div className="coord-box">
                    {/* AREA event: a region centroid, not a source point */}
                    <div className="ttl">Region Centroid · Area Event</div>
                    <div className="coord-row">
                      <span>
                        LAT <b>{detail.lat.toFixed(2)}°N</b>
                      </span>
                      <span>
                        LON <b>{detail.lon.toFixed(2)}°E</b>
                      </span>
                    </div>
                  </div>
                </div>
              )}
              {(detail?.raster || detail?.heat) && (
                <div className="hud" style={{ top: 14, right: 16 }}>
                  <div className="seg">
                    {(detail.heat
                      ? detail.heat.heat_raster.layers
                      : detail.raster?.layers ?? []
                    ).map((l) => (
                      <button
                        key={l}
                        className={layer === l ? "on" : ""}
                        onClick={() => setLayer(l)}
                      >
                        {LAYER_LABELS[l] ?? l}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {detail && (
              <Inspector
                detail={detail}
                hypotheses={hypotheses}
                factors={factors}
                qcal={qcal}
                onQcal={setQcal}
                onResizeStart={onResizeStart}
              />
            )}
          </div>
        </div>
      </div>

      {/* Persistent provenance declaration: this dashboard renders committed,
          reviewed artifacts — there is no live feed, and the chrome says so. */}
      <div className="statusbar">
        <span>AETHER · PLANETARY ENGINE</span>
        <span className="sb-honesty">
          ALL VALUES FROM COMMITTED, REVIEWED ARTIFACTS · NO LIVE TELEMETRY
        </span>
      </div>
    </div>
  );
}
