import type { Metadata } from "next";
import Script from "next/script";
import { Archivo, Chakra_Petch, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

// Self-hosted via next/font (downloaded at build, served first-party; all four
// faces are SIL OFL 1.1 — see docs/reports/redesign_v2_report.md §8).
// Roles: --font-label = Archivo (UI grotesque: labels, buttons, badges, display
// numerals); --font-mono = IBM Plex Mono (data values, codes, tables);
// --font-sans = IBM Plex Sans (prose + honesty text); --font-brand = Chakra
// Petch (brand accent ONLY: wordmark, planetary watermark).
const archivo = Archivo({
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
  variable: "--font-label",
  display: "swap",
});
const chakra = Chakra_Petch({
  weight: ["700"],
  subsets: ["latin"],
  variable: "--font-brand",
  display: "swap",
});
const plexMono = IBM_Plex_Mono({
  weight: ["400", "500", "600"],
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});
const plexSans = IBM_Plex_Sans({
  weight: ["400", "500", "600"],
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AETHER — Planetary Engine",
  description: "Photoreal orbital monitoring: methane super-emitter reconstruction.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${archivo.variable} ${chakra.variable} ${plexMono.variable} ${plexSans.variable}`}
    >
      <head>
        {/* Cesium's widget CSS + prebuilt UMD bundle, served statically from
            public/cesium (copied by scripts/copy-cesium.mjs). Loaded as an
            external script so the Next bundler never touches Cesium. */}
        {/* eslint-disable-next-line @next/next/no-css-tags */}
        <link rel="stylesheet" href="/cesium/Widgets/widgets.css" />
        <Script id="cesium-base-url" strategy="beforeInteractive">
          {`window.CESIUM_BASE_URL = '/cesium';`}
        </Script>
        <Script src="/cesium/Cesium.js" strategy="beforeInteractive" />
      </head>
      <body>{children}</body>
    </html>
  );
}
