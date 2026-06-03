"use client";

// The photoreal globe. Owns all Cesium state. Earth imagery comes from Cesium
// ion (if NEXT_PUBLIC_CESIUM_ION_TOKEN is set) or, token-free, ESRI World
// Imagery. Markers are HTML overlays projected from the 3D scene each frame
// (so they can use the mockup's exact CSS). Selecting an event flies the camera
// in with camera.flyTo, then drapes the real enhancement raster + CC-1213 mask
// outline at their true lon/lat bounds on the dimmed globe.

import { useEffect, useRef } from "react";
import * as Cesium from "cesium";
import type { EventSummary, RasterBounds, RetrievalLayer } from "@/lib/types";
import { maskGeoJsonUrl, rasterUrl } from "@/lib/api";

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

const HOME = Cesium.Cartesian3.fromDegrees(40, 25, 22_000_000);
const ROTATION_RATE = 0.0008; // radians/frame when idle

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
  const viewerRef = useRef<Cesium.Viewer | null>(null);
  const baseLayerRef = useRef<Cesium.ImageryLayer | null>(null);
  const rasterLayerRef = useRef<Cesium.ImageryLayer | null>(null);
  const maskDsRef = useRef<Cesium.GeoJsonDataSource | null>(null);
  const markerEls = useRef<Map<string, HTMLDivElement>>(new Map());
  const markerCarts = useRef<Map<string, Cesium.Cartesian3>>(new Map());
  const autoRotate = useRef(true);
  const draggingRef = useRef(false);
  const prevFly = useRef<FlyTarget | null>(null);

  // Latest callbacks without retriggering the init effect.
  const cb = useRef({ onSelect, onArrived, onReturned });
  cb.current = { onSelect, onArrived, onReturned };

  // ---- init Cesium once ----
  useEffect(() => {
    if (!containerRef.current) return;
    (window as unknown as { CESIUM_BASE_URL: string }).CESIUM_BASE_URL = "/cesium";

    const token = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN;
    if (token) Cesium.Ion.defaultAccessToken = token;

    const viewer = new Cesium.Viewer(containerRef.current, {
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

    const scene = viewer.scene;
    scene.backgroundColor = Cesium.Color.TRANSPARENT;
    scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b1018");
    scene.globe.showGroundAtmosphere = true;
    if (scene.skyAtmosphere) scene.skyAtmosphere.show = true;
    scene.globe.enableLighting = false;
    scene.fog.enabled = true;
    // No default double-click zoom-to-entity (we drive the camera).
    viewer.screenSpaceEventHandler.removeInputAction(
      Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK,
    );

    viewer.camera.setView({ destination: HOME });

    // Pause auto-rotation while the user is dragging.
    const canvas = viewer.canvas;
    const down = () => {
      draggingRef.current = true;
    };
    const up = () => {
      draggingRef.current = false;
    };
    canvas.addEventListener("mousedown", down);
    window.addEventListener("mouseup", up);

    // Earth imagery + auto-spin + marker projection run every frame.
    void applyBody(viewer, "earth", baseLayerRef);

    // Marker culling: a point on the globe is front-facing (not over the horizon)
    // when its direction from Earth's center is within the horizon cone of the
    // sub-camera point — cos(angle) > R/|camera|. Typed sphere approximation of
    // Cesium's EllipsoidalOccluder (which isn't in the public type defs).
    const winPos = new Cesium.Cartesian2();
    const camDirN = new Cesium.Cartesian3();
    const pDirN = new Cesium.Cartesian3();
    const R = scene.globe.ellipsoid.maximumRadius;
    scene.postRender.addEventListener(() => {
      if (autoRotate.current && !draggingRef.current) {
        viewer.camera.rotate(Cesium.Cartesian3.UNIT_Z, ROTATION_RATE);
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

    return () => {
      canvas.removeEventListener("mousedown", down);
      window.removeEventListener("mouseup", up);
      viewer.destroy();
      viewerRef.current = null;
    };
  }, []);

  // ---- body switch ----
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    void applyBody(viewer, body, baseLayerRef);
  }, [body]);

  // ---- update marker cartesians when events change ----
  useEffect(() => {
    markerCarts.current = new Map(
      events.map((e) => [e.event_id, Cesium.Cartesian3.fromDegrees(e.lon, e.lat)]),
    );
  }, [events]);

  // ---- fly to / fly home ----
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer) return;
    const prev = prevFly.current;
    prevFly.current = flyTarget;

    if (flyTarget) {
      autoRotate.current = false;
      const height = frameHeight(flyTarget.bounds);
      viewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(flyTarget.lon, flyTarget.lat, height),
        orientation: {
          heading: 0,
          pitch: Cesium.Math.toRadians(-78),
          roll: 0,
        },
        duration: 1.5,
        complete: () => cb.current.onArrived(),
      });
    } else if (prev) {
      // returning to the globe
      viewer.camera.flyTo({
        destination: HOME,
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
    if (!viewer) return;
    let cancelled = false;

    async function apply() {
      if (!viewer) return;
      // clear previous
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
      // dim the base Earth so the inferno plume pops
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
                className={
                  "marker " + (isActive ? "active" : "pending disabled")
                }
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
  const widthM = (bounds.east - bounds.west) * 111_000 * Math.cos(Cesium.Math.toRadians(midLat));
  const heightM = (bounds.north - bounds.south) * 111_000;
  return Math.max(widthM, heightM) * 1.5;
}

/** Swap base imagery for the selected body. Earth = photoreal; Moon/Mars are
 *  honest placeholders (we have no data there — markers are hidden too). */
async function applyBody(
  viewer: Cesium.Viewer,
  body: "earth" | "moon" | "mars",
  baseLayerRef: React.MutableRefObject<Cesium.ImageryLayer | null>,
): Promise<void> {
  const layers = viewer.imageryLayers;
  if (baseLayerRef.current) {
    layers.remove(baseLayerRef.current, true);
    baseLayerRef.current = null;
  }
  const scene = viewer.scene;
  if (body === "earth") {
    if (scene.skyAtmosphere) scene.skyAtmosphere.show = true;
    scene.globe.showGroundAtmosphere = true;
    const token = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN;
    const provider = token
      ? await Cesium.IonImageryProvider.fromAssetId(2)
      : await Cesium.ArcGisMapServerImageryProvider.fromUrl(
          "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer",
        );
    baseLayerRef.current = layers.addImageryProvider(provider);
  } else {
    // No imagery/data for other bodies yet: a flat tinted sphere, no atmosphere.
    if (scene.skyAtmosphere) scene.skyAtmosphere.show = false;
    scene.globe.showGroundAtmosphere = false;
    scene.globe.baseColor =
      body === "moon"
        ? Cesium.Color.fromCssColorString("#8a8f98")
        : Cesium.Color.fromCssColorString("#8a3a22");
  }
}
