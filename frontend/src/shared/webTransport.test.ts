import { expect, it, vi } from "vitest";

import { createWebTransport } from "./webTransport";

it("maps JSON requests through an injected fetch implementation", async () => {
  const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  const transport = createWebTransport(fetchImpl);

  await expect(
    transport.request<{ ok: boolean }>({
      path: "/api/test",
      method: "POST",
      body: { enabled: true },
    }),
  ).resolves.toEqual({ ok: true });

  expect(fetchImpl).toHaveBeenCalledWith(
    "/api/test",
    expect.objectContaining({
      method: "POST",
      credentials: "include",
      body: JSON.stringify({ enabled: true }),
    }),
  );
});

it("maps multipart parts to browser FormData", async () => {
  const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
    new Response(JSON.stringify({ uploaded: true }), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    }),
  );
  const transport = createWebTransport(fetchImpl);

  await expect(
    transport.upload<{ uploaded: boolean }>({
      path: "/api/upload",
      method: "POST",
      parts: [
        { name: "payload", value: "{}" },
        {
          bytes: new Uint8Array([1, 2, 3]),
          contentType: "application/octet-stream",
          filename: "sample.bin",
          name: "file",
        },
      ],
    }),
  ).resolves.toEqual({ uploaded: true });

  const [, init] = fetchImpl.mock.calls[0];
  expect(new Headers(init?.headers).has("Content-Type")).toBe(false);
  expect(init?.body).toBeInstanceOf(FormData);
  const formData = init?.body as FormData;
  expect(formData.get("payload")).toBe("{}");
  expect(formData.get("file")).toMatchObject({ name: "sample.bin", type: "application/octet-stream" });
  expect(Array.from(new Uint8Array(await (formData.get("file") as File).arrayBuffer()))).toEqual([1, 2, 3]);
});

it("maps binary responses and response metadata", async () => {
  const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(
    new Response(new Uint8Array([80, 68, 70]), {
      status: 200,
      headers: {
        "Content-Disposition": "attachment; filename*=UTF-8''plan%20fa.pdf",
        "Content-Type": "application/pdf",
      },
    }),
  );
  const transport = createWebTransport(fetchImpl);

  const result = await transport.download({ path: "/api/plan.pdf", responseType: "binary" });
  expect(result).toMatchObject({
    contentType: "application/pdf",
    filename: "plan fa.pdf",
  });
  expect(Array.from(result.bytes)).toEqual([80, 68, 70]);
});
