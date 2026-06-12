// Typed client for the Aether dashboard API. Every value the UI shows comes
// through here — nothing is hardcoded in components.
import type {
  EventDetail,
  EventSummary,
  FactorHypothesisSet,
  HypothesisSet,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API ${path} -> ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function fetchEvents(): Promise<EventSummary[]> {
  return getJSON<EventSummary[]>("/api/events");
}

export function fetchEvent(eventId: string): Promise<EventDetail> {
  return getJSON<EventDetail>(`/api/events/${eventId}`);
}

/** The committed source-attribution artifact, or null when none exists (pending). */
export async function fetchHypotheses(eventId: string): Promise<HypothesisSet | null> {
  const body = await getJSON<HypothesisSet | { hypotheses: null; status: string }>(
    `/api/events/${eventId}/hypotheses`,
  );
  return body.hypotheses === null ? null : (body as HypothesisSet);
}

/** URL of a colorized raster layer for an event (served by the API).
 *  Methane retrieval layers live at /<layer>.png (legacy routes); heat field
 *  layers go through the generic whitelisted /layers/<layer>.png route. */
const HEAT_LAYERS = new Set(["air_anomaly", "air_baseline", "lst_anomaly"]);
export function rasterUrl(eventId: string, layer: string): string {
  if (HEAT_LAYERS.has(layer)) return heatLayerUrl(eventId, layer);
  return `${API_BASE}/api/events/${eventId}/${layer}.png`;
}

export function maskGeoJsonUrl(eventId: string): string {
  return `${API_BASE}/api/events/${eventId}/mask.geojson`;
}

/** The committed Stage C factor-attribution artifact, or null (pending/absent). */
export async function fetchFactorHypotheses(
  eventId: string,
): Promise<FactorHypothesisSet | null> {
  const body = await getJSON<FactorHypothesisSet | { factors: null; status: string }>(
    `/api/events/${eventId}/factor-hypotheses`,
  );
  return body.factors === null ? null : (body as FactorHypothesisSet);
}

/** URL of a generic per-event raster layer (heat: air_anomaly/air_baseline/lst_anomaly). */
export function heatLayerUrl(eventId: string, layer: string): string {
  return `${API_BASE}/api/events/${eventId}/layers/${layer}.png`;
}
