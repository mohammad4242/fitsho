import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",

    proxy: {
      "/api": {
        target: "http://localhost:8001",
        changeOrigin: false,
      },
      "^/media(?:/|$)": {
        target: "http://localhost:8001",
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
