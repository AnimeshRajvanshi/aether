import type { Metadata } from "next";
import { Chakra_Petch, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "cesium/Build/Cesium/Widgets/widgets.css";
import "./globals.css";

// Self-hosted via next/font (no Inter/system fallback). These map to the CSS
// variables the ported mockup styles expect: --font-hud / --font-mono / --font-sans.
const chakra = Chakra_Petch({
  weight: ["300", "400", "500", "600", "700"],
  subsets: ["latin"],
  variable: "--font-hud",
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
    <html lang="en" className={`${chakra.variable} ${plexMono.variable} ${plexSans.variable}`}>
      <body>{children}</body>
    </html>
  );
}
