import { expect, it, vi } from "vitest";

import { createSentryCompatibleAdapter, type SentryClientLike } from "./sentryAdapter";

it("maps the provider-neutral adapter to Sentry capture calls", () => {
  const client = {
    captureException: vi.fn(),
    captureMessage: vi.fn(),
  } satisfies SentryClientLike;
  const adapter = createSentryCompatibleAdapter(client);
  const context = { correlation_id: "corr-1", operation: "request" };
  const error = new Error("safe");

  adapter.captureMessage("native_request_completed", "info", context);
  adapter.captureException(error, context);

  expect(client.captureMessage).toHaveBeenCalledWith(
    "native_request_completed",
    { extra: context, level: "info" },
  );
  expect(client.captureException).toHaveBeenCalledWith(error, { extra: context });
});
