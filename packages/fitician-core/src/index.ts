export const FITICIAN_CORE_VERSION = "0.1.0";

export type { components, paths, webhooks } from "./generated/api";
export {
  formatPrescriptionTarget,
  formatTomanInput,
  irrToRoundedToman,
  irrToToman,
  roundToTenThousandToman,
  tomanToIrr,
} from "./formatters";
export {
  GHOST_BACK_PRIVACY_CUT_RATIO,
  GHOST_PRIVACY_CUT_RATIO,
  GHOST_SIDE_PRIVACY_CUT_RATIO,
  clampGhostScale,
  getGhostGeometry,
  ghostPrivacyCutRatioForView,
  ghostPrivacyLineGeometry,
  isPointInZone,
  pointZoneDistance,
  transformGhostPoint,
  transformGhostZone,
} from "./body-ghost";
export type {
  GhostPoint,
  GhostPrivacyLine,
  GhostViewGeometry,
  GhostZone,
} from "./body-ghost";
export {
  GHOST_SCALE_MAX,
  GHOST_SCALE_MIN,
  GHOST_SCALE_STEP,
  PHOTO_SCALE_MAX,
  PHOTO_SCALE_MIN,
  PHOTO_SCALE_STEP,
  stepGhostScale,
} from "./body-ghost-scale";
export {
  GHOST_EDITOR_DEFAULT_TRANSFORM,
  GHOST_EDITOR_OUTPUT,
  GHOST_EDITOR_TOLERANCE,
  clampGhostPhotoTransform,
  containImageRect,
  createGhostPhotoRenderPlan,
  isGhostFramingWithinTolerance,
  privacyCropSourceYForView,
} from "./body-ghost-editor";
export type {
  GhostContainedImageRect,
  GhostDisplaySize,
  GhostPhotoRenderPlan,
  GhostPhotoTransform,
} from "./body-ghost-editor";
export type * from "./profile-validation";
export { ApiError } from "./transport";
export type {
  ApiErrorObject,
  ApiErrorPayload,
  ApiValidationDetail,
  BinaryDownload,
  BinaryDownloadRequest,
  CancellationSignal,
  CursorPage,
  FiticianTransport,
  HttpMethod,
  JsonObject,
  JsonPrimitive,
  JsonValue,
  MultipartPart,
  MultipartUploadRequest,
  Page,
  RequestHeaders,
  TransportRequest,
} from "./transport";
