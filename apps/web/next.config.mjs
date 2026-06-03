/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // NOTE: do NOT add `transpilePackages: ['cesium']`. Cesium ships valid modern
  // ESM and is imported client-only (dynamic, ssr:false). Forcing SWC to
  // transpile its bundled third-party code produces an invalid chunk
  // ("octal escape sequences are not allowed in template strings") that fails
  // to load at runtime. Importing it as-is works.
  env: {
    // Where the API lives. Overridable for non-local deployments.
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000",
  },
};

export default nextConfig;
