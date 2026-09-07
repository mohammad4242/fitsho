import type { GhostDisplaySize } from "@fitician/core/body-ghost-editor";
import type { BodyPhotoSide, BodyPhotoView } from "@fitician/core/body-photos";

import {
  createBodyPhotoPrivacyCropPlan,
} from "./privacyCrop";

export type BodyPhotoCropAction = {
  readonly crop: {
    readonly height: number;
    readonly originX: number;
    readonly originY: number;
    readonly width: number;
  };
};

export type EncodedBodyPhoto = {
  readonly height: number;
  readonly mimeType: string;
  readonly uri: string;
  readonly width: number;
};

export type BodyPhotoPrivacyCropRequest = {
  readonly displaySize?: GhostDisplaySize;
  readonly ghostScale?: number;
  readonly sideProfile?: BodyPhotoSide;
  readonly sourceSize: GhostDisplaySize;
  readonly view: BodyPhotoView;
};

export function createBodyPhotoCropAction(
  input: BodyPhotoPrivacyCropRequest,
): BodyPhotoCropAction {
  const plan = createBodyPhotoPrivacyCropPlan(input);
  return {
    crop: {
      height: plan.outputHeight,
      originX: 0,
      originY: plan.sourceCropY,
      width: plan.outputWidth,
    },
  };
}

export function validateEncodedBodyPhoto(
  encoded: EncodedBodyPhoto,
  input: BodyPhotoPrivacyCropRequest,
): EncodedBodyPhoto {
  const plan = createBodyPhotoPrivacyCropPlan(input);
  if (encoded.mimeType !== "image/jpeg") {
    throw new Error("Privacy-cropped body photo must be JPEG");
  }
  if (encoded.uri.trim().length === 0) {
    throw new Error("Privacy-cropped body photo must have a file URI");
  }
  if (encoded.width !== plan.outputWidth || encoded.height !== plan.outputHeight) {
    throw new Error("Encoded body photo does not match the privacy crop");
  }
  return encoded;
}
