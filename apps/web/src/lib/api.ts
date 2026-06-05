// Typed client for the Aether dashboard API. Every value the UI shows comes
// through here — nothing is hardcoded in components.
import type { EventDetail, EventSummary, HypothesisSet, RetrievalLayer } from "./types";

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

/** URL of a colorized raster layer for an event (served by the API). */
export function rasterUrl(eventId: string, layer: RetrievalLayer): string {
  const file = layer === "enhancement" ? "enhancement.png" : `${layer}.png`;
  return `${API_BASE}/api/events/${eventId}/${file}`;
}

export function maskGeoJsonUrl(eventId: string): string {
  return `${API_BASE}/api/events/${eventId}/mask.geojson`;
}
