import type {
  BodyPhotoPurpose,
  BodyPhotoSession,
} from "@fitician/core/body-photos";
import type { TransportRequest } from "@fitician/core";

export type AuthenticatedBodyPhotoRequest = <TResponse>(
  request: TransportRequest,
) => Promise<TResponse>;

export interface BodyPhotoApi {
  createSession(purpose: BodyPhotoPurpose): Promise<BodyPhotoSession>;
  getSession(sessionId: string): Promise<BodyPhotoSession>;
}

const basePath = "/api/v1/body-photo-sessions";

export function createBodyPhotoApi(request: AuthenticatedBodyPhotoRequest): BodyPhotoApi {
  return {
    createSession: (purpose) => request<BodyPhotoSession>({
      body: { purpose },
      method: "POST",
      path: basePath,
    }),
    getSession: (sessionId) => {
      const normalizedId = sessionId.trim();
      if (normalizedId.length === 0) {
        return Promise.reject(new Error("A body-photo session id is required"));
      }
      return request<BodyPhotoSession>({
        method: "GET",
        path: `${basePath}/${encodeURIComponent(normalizedId)}`,
      });
    },
  };
}
