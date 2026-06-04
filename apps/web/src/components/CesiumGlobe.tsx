"use client";

// The photoreal globe. Owns all Cesium state. Earth imagery comes from Cesium
// ion (if NEXT_PUBLIC_CESIUM_ION_TOKEN is set) or, token-free, ESRI World
// Imagery. Markers are HTML overlays projected from the 3D scene each frame
// (so they can use the mockup's exact CSS). Selecting an event flies the camera
// in with camera.flyTo, then drapes the real enhancement raster + CC-1213 mask
// outline at their true lon/lat bounds on the dimmed globe.
//
// Cesium is loaded as an external UMD script (window.Cesium, see layout.tsx) —
// NOT bundled — because Next's minifier mis-compiles its vendored code. We keep
// full typing via `import type` and read the runtime object from window.

import { useEffect, useRef, useState } from "react";
import type * as CesiumNS from "cesium";
import type { EventSummary, RasterBounds, RetrievalLayer } from "@/lib/types";
import { maskGeoJsonUrl, rasterUrl } from "@/lib/api";

declare global {
  interface Window {
    Cesium: typeof CesiumNS;
  }
}

export interface FlyTarget {
  lon: number;
  lat: number;
  bounds?: RasterBounds;
}

interface Props {
  events: EventSummary[];
  body: "earth" | "moon" | "mars";
  flyTarget: FlyTarget | null;
  raster: { eventId: string; bounds: RasterBounds } | null;
  layer: RetrievalLayer;
  onSelect: (ev: EventSummary) => void;
  onArrived: () => void;
  onReturned: () => void;
}

const ROTATION_RATE = 0.0008; // radians/frame when idle
const toRad = (deg: number) => (deg * Math.PI) / 180;

/** Run cb once window.Cesium (external UMD) is available. */
function whenCesiumReady(cb: () => void): () => void {
  if (typeof window !== "undefined" && window.Cesium) {
    cb();
    return () => {};
  }
  const id = window.setInterval(() => {
    if (window.Cesium) {
      window.clearInterval(id);
      cb();
    }
  }, 50);
  return () => window.clearInterval(id);
}

export default function CesiumGlobe({
  events,
  body,
  flyTarget,
  raster,
  layer,
  onSelect,
  onArrived,
  onReturned,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<CesiumNS.Viewer | null>(null);
  const homeRef = useRef<CesiumNS.Cartesian3 | null>(null);
  const baseLayerRef = useRef<CesiumNS.ImageryLayer | null>(null);
  const rasterLayerRef = useRef<CesiumNS.ImageryLayer | null>(null);
  const maskDsRef = useRef<CesiumNS.GeoJsonDataSource | null>(null);
  const markerEls = useRef<Map<string, HTMLDivElement>>(new Map());
  const markerCarts = useRef<Map<string, CesiumNS.Cartesian3>>(new Map());
  const autoRotate = useRef(true);
  const draggingRef = useRef(false);
  const prevFly = useRef<FlyTarget | null>(null);
  const [ready, setReady] = useState(false);

  const cb = useRef({ onSelect, onArrived, onReturned });
  cb.current = { onSelect, onArrived, onReturned };

  // ---- init Cesium once ----
  useEffect(() => {
    let viewer: CesiumNS.Viewer | null = null;
    let cleanupListeners = () => {};

    const stopWaiting = whenCesiumReady(() => {
      if (!containerRef.current) return;
      const Cesium = window.Cesium;

      const token = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN;
      if (token) Cesium.Ion.defaultAccessToken = token;

      viewer = new Cesium.Viewer(containerRef.current, {
        baseLayer: false,
        baseLayerPicker: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        navigationHelpButton: false,
        animation: false,
        timeline: false,
        fullscreenButton: false,
        selectionIndicator: false,
        infoBox: false,
        scene3DOnly: true,
        contextOptions: { webgl: { alpha: true } },
      });
      viewerRef.current = viewer;
      homeRef.current = Cesium.Cartesian3.fromDegrees(40, 25, 22_000_000);

      const scene = viewer.scene;
      scene.backgroundColor = Cesium.Color.TRANSPARENT;
      scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b1018");
      scene.globe.showGroundAtmosphere = true;
      if (scene.skyAtmosphere) scene.skyAtmosphere.show = true;
      scene.globe.enableLighting = false;
      scene.fog.enabled = true;
      viewer.screenSpaceEventHandler.removeInputAction(
        Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK,
      );
      viewer.camera.setView({ destination: homeRef.current });

      const canvas = viewer.canvas;
      const down = () => (draggingRef.current = true);
      const up = () => (draggingRef.current = false);
      canvas.addEventListener("mousedown", down);
      window.addEventListener("mouseup", up);

      // Marker culling: a point on the globe is front-facing (not over the
      // horizon) when cos(angle to sub-camera point) > R/|camera| — a typed
      // sphere approximation of Cesium's (untyped) EllipsoidalOccluder.
      const winPos = new Cesium.Cartesian2();
      const camDirN = new Cesium.Cartesian3();
      const pDirN = new Cesium.Cartesian3();
      const R = scene.globe.ellipsoid.maximumRadius;
      scene.postRender.addEventListener(() => {
        if (autoRotate.current && !draggingRef.current) {
          viewer!.camera.rotate(Cesium.Cartesian3.UNIT_Z, ROTATION_RATE);
        }
        const camPos = scene.camera.positionWC;
        const horizonCos = R / Cesium.Cartesian3.magnitude(camPos);
        Cesium.Cartesian3.normalize(camPos, camDirN);
        markerEls.current.forEach((el, id) => {
          const cart = markerCarts.current.get(id);
          if (!cart) return;
          Cesium.Cartesian3.normalize(cart, pDirN);
          const frontFacing = Cesium.Cartesian3.dot(camDirN, pDirN) > horizonCos;
          const w = frontFacing
            ? Cesium.SceneTransforms.worldToWindowCoordinates(scene, cart, winPos)
            : undefined;
          if (w) {
            el.style.transform = `translate(${w.x}px, ${w.y}px)`;
            el.style.display = "block";
          } else {
            el.style.display = "none";
          }
        });
      });

      // build initial marker cartesians
      markerCarts.current = new Map(
        events.map((e) => [e.event_id, Cesium.Cartesian3.fromDegrees(e.lon, e.lat)]),
      );

      cleanupListeners = () => {
        canvas.removeEventListener("mousedown", down);
        window.removeEventListener("mouseup", up);
      };

      // Imagery is applied through the single [body, ready] effect below — never
      // from here — so the base layer is added exactly once (no orphaned layer).
      setReady(true);
    });

    return () => {
      stopWaiting();
      cleanupListeners();
      viewer?.destroy();
      viewerRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- body switch (and initial imagery once the viewer is ready) ----
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !ready) return;
    void applyBody(viewer, body, baseLayerRef, rasterLayerRef.current);
  }, [body, ready]);

  // ---- update marker cartesians when events change ----
  useEffect(() => {
    if (!window.Cesium) return;
    const Cesium = window.Cesium;
    markerCarts.current = new Map(
      events.map((e) => [e.event_id, Cesium.Cartesian3.fromDegrees(e.lon, e.lat)]),
    );
  }, [events]);

  // ---- fly to / fly home ----
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !window.Cesium) return;
    const Cesium = window.Cesium;
    const prev = prevFly.current;
    prevFly.current = flyTarget;

    if (flyTarget) {
      autoRotate.current = false;
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(
          flyTarget.lon,
          flyTarget.lat,
          frameHeight(flyTarget.bounds),
        ),
        orientation: { heading: 0, pitch: toRad(-78), roll: 0 },
        duration: 1.5,
        complete: () => cb.current.onArrived(),
      });
    } else if (prev && homeRef.current) {
      viewer.camera.flyTo({
        destination: homeRef.current,
        duration: 1.2,
        complete: () => {
          autoRotate.current = true;
          cb.current.onReturned();
        },
      });
    }
  }, [flyTarget]);

  // ---- raster overlay (drape on globe) + mask outline + dim ----
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !window.Cesium) return;
    const Cesium = window.Cesium;
    let cancelled = false;

    async function apply() {
      if (!viewer) return;
      if (rasterLayerRef.current) {
        viewer.imageryLayers.remove(rasterLayerRef.current, true);
        rasterLayerRef.current = null;
      }
      if (maskDsRef.current) {
        viewer.dataSources.remove(maskDsRef.current, true);
        maskDsRef.current = null;
      }
      if (!raster) {
        if (baseLayerRef.current) baseLayerRef.current.brightness = 1.0;
        return;
      }
      if (baseLayerRef.current) baseLayerRef.current.brightness = 0.32;

      const provider = await Cesium.SingleTileImageryProvider.fromUrl(
        rasterUrl(raster.eventId, layer),
        {
          rectangle: Cesium.Rectangle.fromDegrees(
            raster.bounds.west,
            raster.bounds.south,
            raster.bounds.east,
            raster.bounds.north,
          ),
        },
      );
      if (cancelled || !viewer) return;
      const lyr = viewer.imageryLayers.addImageryProvider(provider);
      lyr.alpha = 0.94;
      rasterLayerRef.current = lyr;

      const ds = await Cesium.GeoJsonDataSource.load(maskGeoJsonUrl(raster.eventId), {
        stroke: Cesium.Color.fromCssColorString("#35d6c3"),
        fill: Cesium.Color.fromCssColorString("#35d6c3").withAlpha(0.05),
        strokeWidth: 3,
        clampToGround: true,
      });
      if (cancelled || !viewer) return;
      viewer.dataSources.add(ds);
      maskDsRef.current = ds;
    }
    void apply();
    return () => {
      cancelled = true;
    };
  }, [raster, layer]);

  // ---- markers (HTML overlays) ----
  return (
    <>
      <div ref={containerRef} id="cesiumContainer" />
      <div className="markers" style={{ display: body === "earth" ? "block" : "none" }}>
        {body === "earth" &&
          events.map((e) => {
            const isActive = e.status === "active";
            return (
              <div
                key={e.event_id}
                ref={(el) => {
                  if (el) markerEls.current.set(e.event_id, el);
                  else markerEls.current.delete(e.event_id);
                }}
                className={"marker " + (isActive ? "active" : "pending disabled")}
                style={{ display: "none" }}
                onClick={isActive ? () => cb.current.onSelect(e) : undefined}
              >
                {isActive && <div className="reticle" />}
                <div className="ring" />
                <div className="dot" />
                <div className="lab">
                  {e.short_name}
                  <span className="sub">{e.headline}</span>
                </div>
              </div>
            );
          })}
      </div>
    </>
  );
}

/** Camera height (m) that frames the raster bounds; sensible default otherwise. */
function frameHeight(bounds?: RasterBounds): number {
  if (!bounds) return 140_000;
  const midLat = (bounds.north + bounds.south) / 2;
  const widthM = (bounds.east - bounds.west) * 111_000 * Math.cos(toRad(midLat));
  const heightM = (bounds.north - bounds.south) * 111_000;
  return Math.max(widthM, heightM) * 1.5;
}

/** Swap base imagery for the selected body. Earth = photoreal; Moon/Mars are
 *  honest placeholders (we have no data there — markers are hidden too). */
async function applyBody(
  viewer: CesiumNS.Viewer,
  body: "earth" | "moon" | "mars",
  baseLayerRef: React.MutableRefObject<CesiumNS.ImageryLayer | null>,
  keep: CesiumNS.ImageryLayer | null,
): Promise<void> {
  const Cesium = window.Cesium;
  const layers = viewer.imageryLayers;
  // Remove every base imagery layer (keep the plume raster overlay if present),
  // so a body switch can never leave an orphaned Earth layer behind.
  for (let i = layers.length - 1; i >= 0; i--) {
    const lyr = layers.get(i);
    if (lyr !== keep) layers.remove(lyr, true);
  }
  baseLayerRef.current = null;
  const scene = viewer.scene;
  if (body === "earth") {
    if (scene.skyAtmosphere) scene.skyAtmosphere.show = true;
    scene.globe.showGroundAtmosphere = true;
    scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b1018");
    const token = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN;
    const provider = token
      ? await Cesium.IonImageryProvider.fromAssetId(2)
      : await Cesium.ArcGisMapServerImageryProvider.fromUrl(
          "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer",
        );
    baseLayerRef.current = layers.addImageryProvider(provider);
  } else {
    // Other bodies are deferred (Earth MVP). Render an unmistakable empty state,
    // NOT a tinted Earth: a plain neutral sphere with no imagery and no
    // atmosphere. The "NO DATA · EARTH MVP" caption is drawn by the UI overlay.
    if (scene.skyAtmosphere) scene.skyAtmosphere.show = false;
    scene.globe.showGroundAtmosphere = false;
    scene.globe.baseColor = Cesium.Color.fromCssColorString("#262b33");
  }
}
