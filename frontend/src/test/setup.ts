import "@testing-library/jest-dom/vitest";
import "../i18n";
import { vi } from "vitest";

Object.defineProperties(HTMLMediaElement.prototype, {
  pause: { configurable: true, value: vi.fn() },
  play: { configurable: true, value: vi.fn().mockResolvedValue(undefined) },
});
