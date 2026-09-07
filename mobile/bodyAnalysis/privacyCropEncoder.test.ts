import { expect, it } from "vitest";

import {
  createBodyPhotoCropAction,
  validateEncodedBodyPhoto,
  type EncodedBodyPhoto,
} from "./privacyCropEncoder";

it("creates an integer crop action from the shared privacy plan", () => {
  expect(createBodyPhotoCropAction({
    ghostScale: 1,
    sourceSize: { height: 2400, width: 1600 },
    view: "front",
  })).toEqual({
    crop: {
      height: 2016,
      originX: 0,
      originY: 384,
      width: 1600,
    },
  });
});

it("validates that the encoded result contains only pixels below the privacy line", () => {
  const encoded: EncodedBodyPhoto = {
    height: 2016,
    mimeType: "image/jpeg",
    uri: "file:///cache/body-front-cropped.jpg",
    width: 1600,
  };

  expect(validateEncodedBodyPhoto(encoded, {
    sourceSize: { height: 2400, width: 1600 },
    view: "front",
  })).toEqual(encoded);
});

it("rejects an encoder result that does not match the shared crop", () => {
  expect(() => validateEncodedBodyPhoto({
    height: 2400,
    mimeType: "image/jpeg",
    uri: "file:///cache/body-front-raw.jpg",
    width: 1600,
  }, {
    sourceSize: { height: 2400, width: 1600 },
    view: "front",
  })).toThrow("privacy crop");
});

it("rejects non-JPEG output from the protected image boundary", () => {
  expect(() => validateEncodedBodyPhoto({
    height: 2016,
    mimeType: "image/png",
    uri: "file:///cache/body-front-cropped.png",
    width: 1600,
  }, {
    sourceSize: { height: 2400, width: 1600 },
    view: "front",
  })).toThrow("JPEG");
});
