import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { ApiError } from "../../shared/apiClient";
import {
  BodyPhotoProcessingError,
  type BodyPhotoProcessor,
  type ProcessedBodyPhoto,
} from "./processor";

const api = vi.hoisted(() => ({
  createBodyPhotoSession: vi.fn(),
  getBodyPhotoSession: vi.fn(),
  uploadBodyPhoto: vi.fn(),
  submitBodyPhotoSession: vi.fn(),
  startBodyPhotoAnalysis: vi.fn(),
}));

const ghostEditor = vi.hoisted(() => ({
  editedFile: new File(["edited"], "body-photo-edited.jpg", { type: "image/jpeg" }),
}));

vi.mock("./api", () => api);
vi.mock("./GhostPhotoEditor", () => ({
  GhostPhotoEditor: ({ onCancel, onConfirm, sideProfile }: {
    onCancel: () => void;
    onConfirm: (file: File) => void;
    sideProfile?: "right" | "left";
  }) => (
    <section aria-labelledby="mock-ghost-editor-title">
      <h3 id="mock-ghost-editor-title">Align your photo</h3>
      <output data-testid="ghost-side-profile">{sideProfile ?? "right"}</output>
      <button type="button" onClick={onCancel}>Cancel editing</button>
      <button type="button" onClick={() => onConfirm(ghostEditor.editedFile)}>Use this photo</button>
    </section>
  ),
}));
vi.mock("./BodyAnalysisRequirementsStep", async () => {
  const { useEffect } = await import("react");
  function MockBodyAnalysisRequirementsStep({ onConfirmed }: { onConfirmed: () => void }) {
    useEffect(() => onConfirmed(), [onConfirmed]);
    return null;
  }
  return { BodyAnalysisRequirementsStep: MockBodyAnalysisRequirementsStep };
});

import { BodyPhotoWizard } from "./BodyPhotoWizard";

const file = new File(["user-photo-bytes"], "front.jpg", { type: "image/jpeg" });

function processed(view: "front" | "side" | "back"): ProcessedBodyPhoto {
  return {
    file: new File([`standardized-${view}`], `${view}.jpg`, { type: "image/jpeg" }),
    previewUrl: `blob:preview-${view}`,
    validation: {
      isValid: true,
      expectedView: view,
      viewAssessment: view === "side" ? "matched" : "ambiguous",
      quality: {
        brightnessScore: 0.9,
        sharpnessScore: 0.9,
        minimumLandmarkVisibility: 0.9,
      },
      visibleLandmarks: ["shoulders", "arms", "hips", "knees", "ankles", "feet"],
    },
  };
}

function serverPhoto(view: "front" | "side" | "back") {
  return {
    id: `${view}-photo`,
    view,
    content_url: `/api/v1/body-photo-sessions/session-2/photos/${view}/content`,
  };
}

function renderWizard(processor?: BodyPhotoProcessor, entry = "/body-progress/new") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <BodyPhotoWizard processor={processor} />
      <LocationDisplay />
    </MemoryRouter>,
  );
}

async function uploadPhoto(user: ReturnType<typeof userEvent.setup>, view: "front" | "side" | "back", photo = file) {
  await user.upload(await screen.findByLabelText(new RegExp(`${view} photo upload`, "i")), photo);
  await user.click(await screen.findByRole("button", { name: /use this photo/i }));
}

function LocationDisplay() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

beforeEach(async () => {
  vi.clearAllMocks();
  await i18n.changeLanguage("en");
  api.createBodyPhotoSession.mockResolvedValue({ id: "session-1", state: "draft", photos: [] });
  api.getBodyPhotoSession.mockResolvedValue({
    id: "session-2",
    state: "failed",
    photos: [],
    operational_processing_consent: { granted: true },
    model_training_consent: { granted: false },
  });
  api.uploadBodyPhoto.mockResolvedValue({ id: "session-1", state: "uploading", photos: [] });
  api.submitBodyPhotoSession.mockResolvedValue({ id: "session-1", state: "queued", photos: [] });
  api.startBodyPhotoAnalysis.mockResolvedValue({ id: "analysis-1", status: "queued" });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

it("keeps the photo workflow optional and offers a skip path", async () => {
  const user = userEvent.setup();
  renderWizard();

  await user.click(screen.getByRole("link", { name: /skip photos/i }));

  expect(screen.getByText(/you can still receive a complete workout plan/i)).toBeInTheDocument();
});

it("requires operational consent before the confirm upload action is enabled", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockResolvedValue(processed("front")) };
  renderWizard(processor);

  await uploadPhoto(user, "front");
  expect(await screen.findByAltText(/standardized front preview/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /confirm and upload front/i })).toBeDisabled();
  expect(api.createBodyPhotoSession).not.toHaveBeenCalled();
  expect(api.uploadBodyPhoto).not.toHaveBeenCalled();

  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  expect(screen.getByRole("button", { name: /confirm and upload front/i })).toBeEnabled();
});

it("does not upload a photo when browser processing rejects it", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = {
    process: vi.fn().mockRejectedValue(new BodyPhotoProcessingError("image_too_blurry")),
  };
  renderWizard(processor);

  await uploadPhoto(user, "front");

  expect(await screen.findByRole("alert")).toHaveTextContent(/too blurry/i);
  expect(api.createBodyPhotoSession).not.toHaveBeenCalled();
  expect(api.uploadBodyPhoto).not.toHaveBeenCalled();
});

it("opens the Ghost editor for uploads and processes only its confirmed output", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockResolvedValue(processed("front")) };
  renderWizard(processor);

  await user.upload(screen.getByLabelText(/front photo upload/i), file);

  expect(await screen.findByRole("heading", { name: /align your photo/i })).toBeInTheDocument();
  expect(processor.process).not.toHaveBeenCalled();

  await user.click(screen.getByRole("button", { name: /use this photo/i }));

  await waitFor(() => expect(processor.process).toHaveBeenCalledWith(ghostEditor.editedFile, "front"));
});

it("toggles the side Ghost from right to left and keeps the selection for upload editing", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = {
    process: vi.fn().mockImplementation((_, selectedView) => processed(selectedView)),
  };
  renderWizard(processor);

  await screen.findByLabelText(/front photo upload/i);
  expect(screen.queryByRole("button", { name: /side profile/i })).not.toBeInTheDocument();

  await uploadPhoto(user, "front");
  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  await user.click(screen.getByRole("button", { name: /confirm and upload front/i }));

  const toggle = await screen.findByRole("button", { name: /side profile: right profile/i });
  expect(toggle).toHaveAttribute("aria-pressed", "false");
  await user.click(toggle);
  expect(toggle).toHaveAttribute("aria-pressed", "true");
  expect(toggle).toHaveTextContent("Left profile");

  await user.upload(screen.getByLabelText(/side photo upload/i), file);
  expect(await screen.findByTestId("ghost-side-profile")).toHaveTextContent("left");
});

it("returns to the existing upload control when the guided camera is unavailable", async () => {
  const user = userEvent.setup();
  renderWizard();

  await user.click(screen.getByRole("button", { name: /use guided camera/i }));

  expect(await screen.findByLabelText(/front photo upload/i)).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent(/camera access needs a secure fitsho address/i);
});

it("explains how to recover when the phone origin is not trusted", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockResolvedValue(processed("front")) };
  api.createBodyPhotoSession.mockRejectedValueOnce(
    new ApiError(403, "Untrusted request origin"),
  );
  renderWizard(processor);

  await uploadPhoto(user, "front");
  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  await user.click(screen.getByRole("button", { name: /confirm and upload front/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    /current phone address is not trusted by fitsho/i,
  );
});

it("replaces only the rejected view in an existing photo session", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockResolvedValue(processed("side")) };
  renderWizard(processor, "/body-progress/new?sessionId=session-2&view=side");

  expect(await screen.findByRole("heading", { name: /side photo/i })).toBeInTheDocument();
  await uploadPhoto(user, "side");
  await user.click(screen.getByRole("button", { name: /confirm and upload side/i }));

  await waitFor(() => expect(api.uploadBodyPhoto).toHaveBeenCalledWith(
    "session-2",
    "side",
    expect.objectContaining({ file: expect.any(File) }),
  ));
  expect(api.createBodyPhotoSession).not.toHaveBeenCalled();
  expect(api.submitBodyPhotoSession).toHaveBeenCalledWith("session-2", true, false);
  expect(api.startBodyPhotoAnalysis).toHaveBeenCalledWith("session-2", true);
});

it("returns to the result after a successful replacement cannot start analysis", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockResolvedValue(processed("side")) };
  api.startBodyPhotoAnalysis.mockRejectedValueOnce(new Error("retry limit"));
  renderWizard(processor, "/body-progress/new?sessionId=session-2&view=side");

  await screen.findByRole("heading", { name: /side photo/i });
  await uploadPhoto(user, "side");
  await user.click(screen.getByRole("button", { name: /confirm and upload side/i }));

  await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("/body-progress/session-2"));
  expect(screen.queryByText(/standardized photo could not be uploaded/i)).not.toBeInTheDocument();
});

it("resumes an incomplete session at its first missing view and submits the same session", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockImplementation((_, view) => processed(view)) };
  api.getBodyPhotoSession.mockResolvedValue({
    id: "session-2",
    state: "uploading",
    photos: [serverPhoto("front")],
    operational_processing_consent: null,
    model_training_consent: null,
    submitted_at: null,
  });
  api.uploadBodyPhoto
    .mockResolvedValueOnce({
      id: "session-2",
      state: "uploading",
      photos: [serverPhoto("front"), serverPhoto("side")],
    })
    .mockResolvedValueOnce({
      id: "session-2",
      state: "uploaded",
      photos: [serverPhoto("front"), serverPhoto("side"), serverPhoto("back")],
    });
  api.submitBodyPhotoSession.mockResolvedValue({
    id: "session-2",
    state: "queued",
    photos: [serverPhoto("front"), serverPhoto("side"), serverPhoto("back")],
  });

  renderWizard(processor, "/body-progress/new?sessionId=session-2");

  await uploadPhoto(user, "side");
  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  await user.click(screen.getByRole("button", { name: /confirm and upload side/i }));
  await uploadPhoto(user, "back");
  await user.click(screen.getByRole("button", { name: /confirm and upload back/i }));

  expect(await screen.findByRole("heading", { name: /review standardized photos/i })).toBeVisible();
  expect(screen.getByAltText(/standardized front preview/i)).toHaveAttribute(
    "src",
    "/api/v1/body-photo-sessions/session-2/photos/front/content",
  );
  await user.click(screen.getByRole("button", { name: /submit photos/i }));

  await waitFor(() => expect(api.submitBodyPhotoSession).toHaveBeenCalledWith("session-2", true, false));
  expect(api.startBodyPhotoAnalysis).toHaveBeenCalledWith("session-2", true);
  expect(api.createBodyPhotoSession).not.toHaveBeenCalled();
  expect(api.uploadBodyPhoto.mock.calls.map((call) => call[1])).toEqual(["side", "back"]);
});

it("opens review directly when an incomplete session already contains three photos", async () => {
  api.getBodyPhotoSession.mockResolvedValue({
    id: "session-2",
    state: "uploaded",
    photos: [serverPhoto("front"), serverPhoto("side"), serverPhoto("back")],
    operational_processing_consent: null,
    model_training_consent: null,
    submitted_at: null,
  });

  renderWizard(undefined, "/body-progress/new?sessionId=session-2");

  expect(await screen.findByRole("heading", { name: /review standardized photos/i })).toBeVisible();
  expect(screen.getAllByRole("img")).toHaveLength(3);
  expect(api.createBodyPhotoSession).not.toHaveBeenCalled();
});

it("shows the selected photo immediately while anonymization is processing", async () => {
  const user = userEvent.setup();
  let resolveProcessing: ((value: ProcessedBodyPhoto) => void) | undefined;
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:selected-front"),
    revokeObjectURL: vi.fn(),
  });
  const processor: BodyPhotoProcessor = {
    process: vi.fn().mockImplementation(() => new Promise<ProcessedBodyPhoto>((resolve) => {
      resolveProcessing = resolve;
    })),
  };
  renderWizard(processor);

  await uploadPhoto(user, "front");

  expect(await screen.findByAltText(/selected front preview/i)).toHaveAttribute(
    "src",
    "blob:selected-front",
  );

  resolveProcessing?.(processed("front"));
});

it("shows fitted-clothing guidance on every capture step", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockImplementation((_, view) => processed(view)) };
  renderWizard(processor);

  expect(screen.getAllByText(/athletic shorts and fitted, minimal athletic clothing/i)).not.toHaveLength(0);
  await uploadPhoto(user, "front");
  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  await user.click(screen.getByRole("button", { name: /confirm and upload front/i }));
  await waitFor(() => expect(screen.getByLabelText(/side photo upload/i)).toBeInTheDocument());
  expect(screen.getByText(/athletic shorts and fitted, minimal athletic clothing/i)).toBeInTheDocument();
});

it("explains Ghost framing and lists every retained body region", async () => {
  await i18n.changeLanguage("fa");
  renderWizard();

  expect(screen.getByText("عکس را زیر راهنمای Ghost قرار بده")).toBeVisible();
  expect(screen.getByLabelText(/راهنمای کادر عکس Ghost/)).toHaveTextContent(
    /شانه‌ها.*بازوها.*کمر و باسن.*زانوها.*مچ پا و کف پا/,
  );
  expect(screen.queryByRole("button", { name: /گرفتن عکس/ })).not.toBeInTheDocument();
  expect(screen.getByLabelText(/بارگذاری عکس روبه‌رو/)).toBeInTheDocument();
});

it("processes three views, allows retake, and uploads only standardized files", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockImplementation((_, view) => processed(view)) };
  renderWizard(processor);

  await uploadPhoto(user, "front");
  await user.click(screen.getByRole("button", { name: /retake front/i }));
  expect(screen.queryByAltText(/standardized front preview/i)).not.toBeInTheDocument();
  await uploadPhoto(user, "front");
  await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
  await user.click(screen.getByRole("button", { name: /confirm and upload front/i }));
  await uploadPhoto(user, "side");
  await user.click(screen.getByRole("button", { name: /confirm and upload side/i }));
  await uploadPhoto(user, "back");
  await user.click(screen.getByRole("button", { name: /confirm and upload back/i }));

  await waitFor(() => expect(api.uploadBodyPhoto).toHaveBeenCalledTimes(3));
  const sentFiles = api.uploadBodyPhoto.mock.calls.map((call) => call[2].file as File);
  expect(sentFiles).not.toContain(file);
  expect(sentFiles.map((item) => item.name)).toEqual(["front.jpg", "side.jpg", "back.jpg"]);
  expect(screen.getByRole("checkbox", { name: /future model-training/i })).not.toBeChecked();
});

it("starts analysis immediately after a successful submission", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockImplementation((_, view) => processed(view)) };
  renderWizard(processor);

  for (const view of ["front", "side", "back"] as const) {
    await uploadPhoto(user, view);
    if (view === "front") {
      await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
    }
    await user.click(screen.getByRole("button", { name: new RegExp(`confirm and upload ${view}`, "i") }));
  }

  await user.click(await screen.findByRole("button", { name: /submit photos/i }));
  await waitFor(() => expect(api.startBodyPhotoAnalysis).toHaveBeenCalledWith("session-1", true));
});

it("explains that photos were submitted when body analysis cannot start", async () => {
  const user = userEvent.setup();
  const processor: BodyPhotoProcessor = { process: vi.fn().mockImplementation((_, view) => processed(view)) };
  api.startBodyPhotoAnalysis.mockRejectedValue(new ApiError(503, "Body photo analysis is temporarily unavailable"));
  renderWizard(processor);

  for (const view of ["front", "side", "back"] as const) {
    await uploadPhoto(user, view);
    if (view === "front") {
      await user.click(screen.getByRole("checkbox", { name: /body-photo privacy and processing terms/i }));
    }
    await user.click(screen.getByRole("button", { name: new RegExp(`confirm and upload ${view}`, "i") }));
  }

  await user.click(await screen.findByRole("button", { name: /submit photos/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent(
    /photos were submitted successfully, but body analysis has not started/i,
  );
  expect(api.submitBodyPhotoSession).toHaveBeenCalledWith("session-1", true, false);
});

it("revokes standardized preview URLs when a photo is replaced and on unmount", async () => {
  const user = userEvent.setup();
  const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  const processor: BodyPhotoProcessor = {
    process: vi.fn()
      .mockResolvedValueOnce(processed("front"))
      .mockResolvedValueOnce({ ...processed("front"), previewUrl: "blob:replacement" }),
  };
  const rendered = renderWizard(processor);

  await uploadPhoto(user, "front");
  await uploadPhoto(user, "front");
  expect(revoke).toHaveBeenCalledWith("blob:preview-front");

  rendered.unmount();
  expect(revoke).toHaveBeenCalledWith("blob:replacement");
});

it("shows only measured quality feedback for a standardized preview", async () => {
  const user = userEvent.setup();
  renderWizard({ process: vi.fn().mockResolvedValue(processed("front")) });

  await uploadPhoto(user, "front");

  expect(screen.getByLabelText(/photo check/i)).toHaveTextContent(/lighting/i);
  expect(screen.getByLabelText(/photo check/i)).toHaveTextContent(/landmark visibility/i);
  expect(screen.getByLabelText(/photo check/i)).not.toHaveTextContent(/overall quality/i);
});

it.each([
  ["shoulders_not_visible", /shoulders are not fully visible/i],
  ["legs_or_feet_not_visible", /legs, ankles, and feet must remain fully inside/i],
  ["body_out_of_frame", /part of the body is outside the frame/i],
  ["image_too_blurry", /image is too blurry/i],
  ["insufficient_lighting", /lighting is not sufficient/i],
  ["unexpected_body_view", /does not match the required view/i],
  ["multiple_people_detected", /more than one person was detected/i],
] as const)("shows the actionable %s error", async (code, message) => {
  const user = userEvent.setup();
  renderWizard({ process: vi.fn().mockRejectedValue(new BodyPhotoProcessingError(code)) });
  await uploadPhoto(user, "front");
  expect(await screen.findByRole("alert")).toHaveTextContent(message);
});

it("releases a late preview when processing resolves after the wizard unmounts", async () => {
  const user = userEvent.setup();
  const revoke = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  let resolveProcessing: ((value: ProcessedBodyPhoto) => void) | undefined;
  const processor: BodyPhotoProcessor = {
    process: vi.fn().mockImplementation(() => new Promise<ProcessedBodyPhoto>((resolve) => {
      resolveProcessing = resolve;
    })),
  };
  const rendered = renderWizard(processor);

  await uploadPhoto(user, "front");
  rendered.unmount();
  resolveProcessing?.({ ...processed("front"), previewUrl: "blob:late-preview" });

  await waitFor(() => expect(revoke).toHaveBeenCalledWith("blob:late-preview"));
});
