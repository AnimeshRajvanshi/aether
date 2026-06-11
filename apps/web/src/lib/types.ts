// Types mirroring apps/api response models (aether_api/models.py). Kept in sync
// by hand — the API is the source of truth; the frontend never invents values.

export type EventStatus = "active" | "pending";

export interface EventSummary {
  event_id: string;
  name: string;
  short_name: string;
  planetary_body: string;
  phenomenon_type: string;
  lat: number;
  lon: number;
  status: EventStatus;
  sensor: string;
  validation_tier: string | null; // VALIDATED | CROSS-CHECKED | DEMONSTRATION | null (pending)
  headline: string | null;
  acquisition_utc: string | null;
}

export interface CalibratedRate {
  label: string;
  value_t_hr: number;
  range_low_t_hr: number;
  range_high_t_hr: number;
  sigma_fractional: number;
  note: string;
}

export interface Quantification {
  ours_cal: CalibratedRate;
  nasa_cal: CalibratedRate;
  enhancement_bias_factor: number;
  central_p_value: number;
}

export interface UncertaintyTerm {
  key: string;
  label: string;
  kind: "symmetric" | "systematic";
  value_pct: number | null;
  factor: number | null;
  display: string;
  bar_fraction: number;
}

export interface Geometry {
  ime_t: number;
  area_km2: number;
  length_km: number;
  centroid_lat: number;
  centroid_lon: number;
}

export interface Atmosphere {
  u10_speed_ms: number;
  u_eff_ms: number;
  era5_grid_lat: number;
  era5_grid_lon: number;
  era5_nearest_hour_utc: string;
}

export interface Validation {
  pearson_in_bbox: number;
  pearson_full_scene: number;
  n_pixels_bbox: number;
  reference_product: string;
  note: string;
  integrated_mass_ratio: number | null;
  pixel_pearson: number | null;
}

export interface ScopeCaveat {
  kind: string; // "cluster_fraction" | "context_only"
  reference_total_t_hr: number;
  reference_uncertainty_t_hr: number | null;
  n_sources: number | null;
  fraction_low_pct: number | null;
  fraction_high_pct: number | null;
  text: string;
}

export interface Reference {
  citation: string;
  doi: string | null;
  url: string | null;
}

export interface Provenance {
  acquisition_utc: string;
  l1b_granule_ur: string | null;
  l2a_mask_granule_ur: string | null;
  l2b_ch4_granule_ur: string | null;
  target_spectrum_source: string | null;
  bands_used: number | null;
  localization: string | null;
}

export interface RasterBounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface RasterMeta {
  bounds: RasterBounds;
  colormap: string;
  vmin_ppm_m: number;
  vmax_ppm_m: number;
  layers: string[];
}

export interface EventDetail {
  event_id: string;
  name: string;
  short_name: string;
  planetary_body: string;
  phenomenon_type: string;
  lat: number;
  lon: number;
  status: EventStatus;
  location_label: string;
  chips: string[];
  validation_tier: string | null;
  tier_explainer: string | null;
  quantification: Quantification | null;
  uncertainty_budget: UncertaintyTerm[];
  geometry: Geometry | null;
  atmosphere: Atmosphere | null;
  validation: Validation | null;
  scope_caveat: ScopeCaveat | null;
  brief: string | null;
  raster: RasterMeta | null;
  provenance: Provenance | null;
  references: Reference[];
  pending_reason: string | null;
}

export type RetrievalLayer = "enhancement" | "nasa" | "diff";

// ---- Source attribution (Sprint 4 artifact, served verbatim by the API) ----
// These mirror aether_causal.schema; every string is rendered verbatim.

export interface ScoreComponent {
  name: string;
  value: number;
  weight: number;
  rationale: string;
  contribution: number;
}

export interface AttributionSourceRef {
  dataset: string;
  locator: string;
  ogim_id: number | null;
  ogim_layer: string | null;
}

export interface EvidenceItem {
  kind: string;
  statement: string;
  source: AttributionSourceRef;
  temporal_caveat: string | null;
}

export interface AttributionCandidate {
  kind: string;
  descriptor: string;
  ogim_layer: string | null;
  ogim_id: number | null;
  ogim_name: string | null;
  operator: string | null;
}

export interface SourceHypothesis {
  id: string;
  rank: number;
  candidate: AttributionCandidate;
  claim: string;
  confidence_tier: string;
  confidence_rationale: string;
  score: number;
  score_components: ScoreComponent[];
  evidence: EvidenceItem[];
  assumptions: string[];
  counter_considerations: string[];
  falsification: string;
  generation_method: string;
}

export interface HypothesisSet {
  event_id: string;
  phenomenon: string;
  generated_method: string;
  headline_finding: string;
  scoring_disclaimer: string;
  confidence_cap: string;
  plume_summary: Record<string, string>;
  global_assumptions: string[];
  hypotheses: SourceHypothesis[];
  provenance: Record<string, string>;
}
