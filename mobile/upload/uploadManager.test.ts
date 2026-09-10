import { expect, it, vi } from "vitest";

import { ApiError } from "@fitician/core";
import type { UploadExecutor, UploadOperation } from "./uploadManager";
import { MobilePerformanceRecorder } from "../platform/performance";

import {
  createTransportUploadExecutor,
  UploadCancellationError,
  UploadManager,
} from "./uploadManager";

vi.mock("expo-crypto", () => ({
  randomUUID: vi.fn(() => "generated-idempotency-key"),
}));

function job(operation: UploadOperation = "tracking") {
  return {
    operation,
    path: "/api/v1/upload",
    parts: [
      {
        bytes: Uint8Array.from([1, 2, 3]),
        contentType: "application/octet-stream",
        filename: "payload.bin",
        name: "file",
      },
    ],
  } as const;
}

it("attempts protected uploads when reachability is stale instead of queueing them", async () => {
  const executor = vi.fn(async <TResponse>() => ({ uploaded: true }) as TResponse);
  const manager = new UploadManager({
    executor: executor as unknown as UploadExecutor,
    isOnline: () => false,
  });

  for (const operation of ["photo", "medical", "consent", "plan-edit"] as const) {
    const handle = manager.enqueue<{ uploaded: boolean }>({
      ...job(operation),
      idempotencyKey: `${operation}-upload-key`,
    });
    await expect(handle.promise).resolves.toEqual({ uploaded: true });
  }
  expect(executor).toHaveBeenCalledTimes(4);
});

it("queues safe tracking uploads and flushes each idempotency key once after reconnect", async () => {
  let online = false;
  const executor = vi.fn(async <TResponse>(request: { headers?: Record<string, string> }) => {
    return { key: request.headers?.["Idempotency-Key"] } as TResponse;
  });
  const manager = new UploadManager({
    executor: executor as unknown as UploadExecutor,
    isOnline: () => online,
  });

  const handle = manager.enqueue({ ...job(), idempotencyKey: "tracking-key-1" });
  const duplicate = manager.enqueue({ ...job(), idempotencyKey: "tracking-key-1" });
  expect(duplicate.id).toBe(handle.id);
  expect(duplicate.promise).toBe(handle.promise);
  expect(handle.getSnapshot().status).toBe("queued");

  online = true;
  await manager.reconnect();
  await expect(handle.promise).resolves.toEqual({ key: "tracking-key-1" });
  await manager.reconnect();

  expect(executor).toHaveBeenCalledOnce();
  expect(executor.mock.calls[0][0].headers).toMatchObject({
    "Idempotency-Key": "tracking-key-1",
  });
});

it("keeps a retryable safe upload queued with the same key", async () => {
  let calls = 0;
  let online = true;
  const executor = vi.fn(async <TResponse>(
    _request: unknown,
    _reportProgress: unknown,
    _signal: unknown,
  ) => {
    calls += 1;
    if (calls === 1) {
      throw new ApiError(503, "temporarily unavailable");
    }
    return { uploaded: true } as TResponse;
  });
  const manager = new UploadManager({
    executor: executor as unknown as UploadExecutor,
    isOnline: () => online,
  });
  const handle = manager.enqueue({ ...job(), idempotencyKey: "tracking-key-2" });

  await Promise.resolve();
  expect(handle.getSnapshot().status).toBe("queued");
  online = false;
  await manager.reconnect();
  online = true;
  await manager.reconnect();

  await expect(handle.promise).resolves.toEqual({ uploaded: true });
  expect(executor).toHaveBeenCalledTimes(2);
  expect(executor.mock.calls[0]?.[0]).toEqual(executor.mock.calls[1]?.[0]);
});

it("records upload duration without retaining multipart payloads", async () => {
  const performance = new MobilePerformanceRecorder(() => 0);
  const manager = new UploadManager({
    executor: async <TResponse>() => ({ uploaded: true }) as TResponse,
    isOnline: () => true,
    performanceRecorder: performance,
  });

  const handle = manager.enqueue({ ...job(), idempotencyKey: "tracking-key-performance" });
  await expect(handle.promise).resolves.toEqual({ uploaded: true });

  expect(performance.getSamples()).toEqual([
    {
      budget: 30_000,
      metric: "upload",
      passed: true,
      unit: "ms",
      value: 0,
    },
  ]);
  expect(JSON.stringify(performance.getSamples())).not.toContain("payload.bin");
});

it("reports progress through the default transport upload adapter", async () => {
  const transport = {
    download: async () => ({ bytes: new Uint8Array(), contentType: null, filename: null }),
    request: async <TResponse>(): Promise<TResponse> => ({}) as TResponse,
    upload: async <TResponse>(): Promise<TResponse> => ({ uploaded: true }) as TResponse,
  };
  const report = vi.fn();
  const executor = createTransportUploadExecutor(transport);

  await expect(
    executor(
      {
        method: "POST",
        parts: job().parts,
        path: job().path,
      },
      report,
      { aborted: false },
    ),
  ).resolves.toEqual({ uploaded: true });
  expect(report).toHaveBeenNthCalledWith(1, 0);
  expect(report).toHaveBeenNthCalledWith(2, 3);
});

it("validates payloads and exposes cancellation state", async () => {
  const manager = new UploadManager({
    executor: async () => {
      throw new UploadCancellationError();
    },
    isOnline: () => true,
  });

  expect(() =>
    manager.enqueue({
      ...job(),
      parts: [{ ...job().parts[0], bytes: new Uint8Array() }],
    }),
  ).toThrow("at least one non-empty file");

  const handle = manager.enqueue(job());
  await expect(handle.promise).rejects.toBeInstanceOf(UploadCancellationError);
  expect(handle.getSnapshot().status).toBe("cancelled");
});
