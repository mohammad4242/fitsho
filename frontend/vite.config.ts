import react from "@vitejs/plugin-react";
import { VitePWA, type ManifestOptions } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

export function resolveApiProxyTarget(value: string | undefined): string {
  return value?.trim() || "http://localhost:8001";
}

const apiProxyTarget = resolveApiProxyTarget(process.env.VITE_API_PROXY_TARGET);

export const pwaManifest = {
  name: "Fitician | فیتیشن",
  short_name: "Fitician",
  description: "فیتیشن؛ همراه هوشمند تمرین، تغذیه و تحلیل بدن.",
  lang: "fa",
  dir: "rtl",
  start_url: "/",
  scope: "/",
  display: "standalone",
  background_color: "#020607",
  theme_color: "#020607",
  icons: [
    { src: "/pwa/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
    { src: "/pwa/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    { src: "/pwa/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
  ],
} satisfies Partial<ManifestOptions>;

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "prompt",
      manifest: pwaManifest,
      workbox: {
        cleanupOutdatedCaches: true,
        globPatterns: ["**/*.{js,css,html,woff,woff2}"],
        globIgnores: [
          "**/fitsho_*_report*.html",
          "**/workout_engine_*.html",
          "**/exercises/**",
          "**/image&videos/**",
          "**/mediapipe/**",
          "**/heic-*.js",
          "**/api/**",
          "**/media/**",
        ],
        additionalManifestEntries: [
          { url: "/pwa/apple-touch-icon.png", revision: null },
        ],
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api(?:\/|$)/, /^\/media(?:\/|$)/],
      },
    }),
  ],
  server: {
    host: "0.0.0.0",

    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: false,
      },
      "^/media(?:/|$)": {
        target: apiProxyTarget,
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true,
    exclude: ["**/node_modules/**", "e2e/**"],
  },
});
