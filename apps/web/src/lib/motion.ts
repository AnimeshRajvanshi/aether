// Shared motion constants. The camera flyTo and the inspector panel slide are
// driven by the SAME duration so they read as one synchronized motion: the
// CesiumGlobe flyTo uses FLY_DURATION_S directly, and Dashboard injects it into
// CSS via the --fly-duration custom property (so there is no separate hardcoded
// CSS duration that merely approximates it).

/** Seconds. The camera flyTo duration AND the panel slide duration, both ways. */
export const FLY_DURATION_S = 1.5;

/** CSS easing that mirrors Cesium's EasingFunction.QUADRATIC_IN_OUT (Penner
 *  easeInOutQuad), so the panel's curve matches the camera's. */
export const FLY_EASING_CSS = "cubic-bezier(0.455, 0.03, 0.515, 0.955)";

// Resizable inspector clamps (in-memory for the session; no localStorage).
export const PANEL_DEFAULT_W = 392;
export const PANEL_MIN_W = 320;
export const PANEL_MAX_W = 620;
/** Keep at least this much width for the globe/plume stage when resizing. */
export const STAGE_MIN_W = 460;

/** Clamp a candidate panel width against both the min/max and the stage floor. */
export function clampPanelWidth(candidate: number, viewportW: number): number {
  const max = Math.min(PANEL_MAX_W, viewportW - STAGE_MIN_W);
  return Math.max(PANEL_MIN_W, Math.min(max, candidate));
}
