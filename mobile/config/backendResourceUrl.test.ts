import { expect, it } from "vitest";

import { resolveBackendResourceUrl } from "./backendResourceUrl";

const API_BASE_URL = "https://api.fitician.test";

it("resolves relative resources against the configured backend", () => {
  expect(resolveBackendResourceUrl("/media/photo.jpg?v=1", API_BASE_URL)).toBe(
    "https://api.fitician.test/media/photo.jpg?v=1",
  );
});

it("allows an absolute resource only when it uses the configured backend origin", () => {
  expect(resolveBackendResourceUrl("https://api.fitician.test/media/photo.jpg", API_BASE_URL)).toBe(
    "https://api.fitician.test/media/photo.jpg",
  );
});

it("rejects resources that would escape the configured backend", () => {
  expect(() => resolveBackendResourceUrl("https://cdn.example/photo.jpg", API_BASE_URL)).toThrow(
    /configured backend origin/u,
  );
  expect(() => resolveBackendResourceUrl("//cdn.example/photo.jpg", API_BASE_URL)).toThrow(
    /configured backend origin/u,
  );
  expect(() => resolveBackendResourceUrl("file:///private/photo.jpg", API_BASE_URL)).toThrow(
    /configured backend origin/u,
  );
});
