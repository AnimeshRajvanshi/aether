/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Cesium ships a large ESM build; let Next transpile it cleanly.
  transpilePackages: ["cesium"],
  env: {
    // Where the API lives. Overridable for non-local deployments.
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000",
  },
};

export default nextConfig;
