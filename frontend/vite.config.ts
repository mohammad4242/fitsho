import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export function resolveApiProxyTarget(value: string | undefined): string {
  return value?.trim() || "http://localhost:8001";
}

const apiProxyTarget = resolveApiProxyTarget(process.env.VITE_API_PROXY_TARGET);

export default defineConfig({
  plugins: [react()],
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
  },
});
