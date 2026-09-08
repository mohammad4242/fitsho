import { afterEach, expect, it, vi } from "vitest";

const runtimeLogger = vi.hoisted(() => ({
  logDevelopmentDiagnostic: vi.fn(),
}));

vi.mock("expo-constants", () => ({
  default: {
    expoConfig: {
      extra: {
        apiBaseUrl: "http://10.0.2.2:8001",
        environment: "development",
      },
    },
  },
}));
vi.mock("../platform/logging", () => runtimeLogger);

import {
  getMobileRuntimeConfig,
  logMobileRuntimeConfiguration,
} from "./nativeRuntimeConfig";

afterEach(() => {
  runtimeLogger.logDevelopmentDiagnostic.mockClear();
});

it("logs the resolved development API target once and warns about emulator-only hosts", () => {
  const config = getMobileRuntimeConfig();
  expect(config).toMatchObject({
    apiBaseUrl: "http://10.0.2.2:8001",
    environment: "development",
  });

  logMobileRuntimeConfiguration(config);
  logMobileRuntimeConfiguration(config);
  logMobileRuntimeConfiguration({ ...config, environment: "production" });

  expect(runtimeLogger.logDevelopmentDiagnostic).toHaveBeenCalledTimes(2);
  expect(runtimeLogger.logDevelopmentDiagnostic).toHaveBeenNthCalledWith(
    1,
    "runtime_configuration",
    "info",
    {
      api_base_url: "http://10.0.2.2:8001",
      environment: "development",
    },
  );
  expect(runtimeLogger.logDevelopmentDiagnostic).toHaveBeenNthCalledWith(
    2,
    "emulator_only_api_target",
    "warning",
    {
      api_base_url: "http://10.0.2.2:8001",
      target: "android_emulator_only",
    },
  );
});
