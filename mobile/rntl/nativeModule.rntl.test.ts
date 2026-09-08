import { expect, jest, test } from "@jest/globals";

jest.mock("react-native-nitro-modules", () => ({
  NitroModules: {
    createHybridObject: jest.fn(),
    hasHybridObject: jest.fn(),
  },
}));

import { NitroModules } from "react-native-nitro-modules";

import { getNativeBodyVision } from "../bodyAnalysis/nativeBodyVision";

test("returns null without the native registry and binds the registered object", () => {
  const nitro = NitroModules as unknown as {
    createHybridObject: ReturnType<typeof jest.fn>;
    hasHybridObject: ReturnType<typeof jest.fn>;
  };
  nitro.hasHybridObject.mockReturnValue(false);

  expect(getNativeBodyVision()).toBeNull();

  const nativeObject = {
    benchmark: jest.fn(),
    contractVersion: "1.0",
    modelStatus: "ready",
    process: jest.fn(),
    recordDroppedFrame: jest.fn(),
  };
  nitro.hasHybridObject.mockReturnValue(true);
  nitro.createHybridObject.mockReturnValue(nativeObject);

  expect(getNativeBodyVision()).toBe(nativeObject);
  expect(nitro.createHybridObject).toHaveBeenCalledWith("FiticianBodyVision");
});
