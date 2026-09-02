import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import type { BodyPhotoProcessor, ProcessedBodyPhoto } from "./processor";

const camera = vi.hoisted(() => ({
  file: new File(["camera"], "camera.jpg", { type: "image/jpeg" }),
}));
const api = vi.hoisted(() => ({
  createBodyPhotoSession: vi.fn(),
  getBodyPhotoSession: vi.fn(),
  uploadBodyPhoto: vi.fn(),
}));

vi.mock("./api", () => api);
vi.mock("./BodyAnalysisRequirementsStep", async () => {
  const { useEffect } = await import("react");
  function MockRequirements({ onConfirmed }: { onConfirmed: () => void }) {
    useEffect(() => onConfirmed(), [onConfirmed]);
    return null;
  }
  return { BodyAnalysisRequirementsStep: MockRequirements };
});
vi.mock("./GhostCameraCapture", () => ({
  GhostCameraCapture: ({ onFileCaptured }: { onFileCaptured: (file: File) => void }) => (
    <button type="button" onClick={() => onFileCaptured(camera.file)}>
      Test camera capture
    </button>
  ),
}));

import { BodyPhotoWizard } from "./BodyPhotoWizard";

function processed(): ProcessedBodyPhoto {
  return {
    file: new File(["standardized"], "standardized.jpg", { type: "image/jpeg" }),
    previewUrl: "blob:standardized",
    validation: {
      isValid: true,
      expectedView: "front",
      viewAssessment: "ambiguous",
      quality: {
        brightnessScore: 0.9,
        sharpnessScore: 0.9,
        minimumLandmarkVisibility: 0.9,
      },
      visibleLandmarks: ["shoulders", "arms", "hips", "knees", "ankles", "feet"],
    },
  };
}

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage("en");
  api.createBodyPhotoSession.mockResolvedValue({ id: "session-1", state: "draft", photos: [] });
  api.uploadBodyPhoto.mockResolvedValue({ id: "session-1", state: "uploading", photos: [] });
});

it("sends a camera file through the same processor used by upload", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockResolvedValue(processed()) };
  render(
    <MemoryRouter initialEntries={["/body-progress/new"]}>
      <BodyPhotoWizard processor={processor} />
    </MemoryRouter>,
  );

  await user.click(await screen.findByRole("button", { name: /use guided camera/i }));
  await user.click(screen.getByRole("button", { name: /test camera capture/i }));

  await waitFor(() => expect(processor.process).toHaveBeenCalledWith(camera.file, "front"));
});
