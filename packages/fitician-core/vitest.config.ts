import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    exclude: ["src/**/*.contract.test.ts"],
    include: ["src/**/*.test.ts"],
  },
});
