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
  headline: string | null;
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
}

export interface ScopeCaveat {
  reference_total_t_hr: number;
  reference_uncertainty_t_hr: number;
  n_sources: number;
  fraction_low_pct: number;
  fraction_high_pct: number;
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
