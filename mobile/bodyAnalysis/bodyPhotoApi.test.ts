import { expect, it, vi } from "vitest";

import { createBodyPhotoApi } from "./bodyPhotoApi";

it("uses the shared body-photo session endpoints", async () => {
  const request = vi.fn().mockResolvedValue({ id: "session-1" });
  const api = createBodyPhotoApi(request);

  await api.createSession("initial_plan");
  await api.getSession("session-1");

  expect(request).toHaveBeenNthCalledWith(1, {
    body: { purpose: "initial_plan" },
    method: "POST",
    path: "/api/v1/body-photo-sessions",
  });
  expect(request).toHaveBeenNthCalledWith(2, {
    method: "GET",
    path: "/api/v1/body-photo-sessions/session-1",
  });
});

it("rejects an empty session id before making a request", async () => {
  const request = vi.fn();
  const api = createBodyPhotoApi(request);

  await expect(api.getSession(" ")).rejects.toThrow("session id");
  expect(request).not.toHaveBeenCalled();
});
