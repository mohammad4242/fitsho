import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import type { ExerciseDetail } from "./types";

const api = vi.hoisted(() => ({ getExercise: vi.fn() }));

vi.mock("./api", () => api);
vi.mock("../../shared/AuthenticatedHeader", () => ({
  AuthenticatedHeader: () => null,
}));

import { ExerciseDetailPage } from "./ExerciseDetailPage";

const detail: ExerciseDetail = {
  id: "018f0000-0000-7000-8000-000000000001",
  slug: "dumbbell-bench-press",
  name_en: "Dumbbell Bench Press",
  name_fa: "پرس سینه دمبل",
  content_type: "exercise",
  body_region: "upper_body",
  primary_muscle: "chest",
  muscle_focus: "mid_chest",
  labels: [],
  secondary_muscles: ["triceps", "shoulders"],
  equipment: ["dumbbell", "bench"],
  difficulty: "intermediate",
  instructions_en: [
    "Lie on a flat bench with both feet planted.",
    "Lower the dumbbells with control beside the chest.",
    "Press upward without locking the elbows hard.",
  ],
  instructions_fa: [
    "روی نیمکت صاف دراز بکش و هر دو پا را روی زمین نگه دار.",
    "دمبل‌ها را با کنترل کنار سینه پایین بیاور.",
    "دمبل‌ها را بالا ببر، بدون اینکه آرنج‌ها را با فشار قفل کنی.",
  ],
  safety_notes_en: [
    "Keep the shoulders supported by the bench.",
    "Use a load you can control through the full range.",
  ],
  safety_notes_fa: [
    "شانه‌ها را روی نیمکت ثابت نگه دار.",
    "وزنه‌ای انتخاب کن که در تمام دامنه کنترلش کنی.",
  ],
  media_path: "/exercises/upper-body/chest/dumbbell-bench-press.gif",
  media_type: "gif",
  media_source_url: null,
  media_license: "Project owner supplied and authorized",
  media_attribution: "Provided by Fitsho project owner",
};

beforeEach(async () => {
  api.getExercise.mockReset();
  api.getExercise.mockResolvedValue(detail);
  await i18n.changeLanguage("fa");
});

afterEach(() => vi.clearAllMocks());

describe("exercise detail states", () => {
  it("uses the supplied strength still above the exercise detail", async () => {
    renderDetail();

    const background = await screen.findByTestId("member-header-image");
    expect(background).toHaveAttribute(
      "src",
      expect.stringContaining("hero-strength-fallback"),
    );
    expect(background.parentElement).toHaveClass("member-page-background");
  });

  it("shows a loading state while the exercise is requested", async () => {
    const pending = deferred<ExerciseDetail | null>();
    api.getExercise.mockReturnValue(pending.promise);
    renderDetail();

    const message = await screen.findByText("در حال دریافت جزئیات حرکت…");
    expect(message.closest('[role="status"]')).toBeInTheDocument();

    pending.resolve(detail);
    expect(await screen.findByRole("heading", { name: "پرس سینه دمبل" })).toBeVisible();
  });

  it("retries a failed request", async () => {
    const user = userEvent.setup();
    api.getExercise
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(detail);
    renderDetail();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "جزئیات حرکت دریافت نشد",
    );
    await user.click(screen.getByRole("button", { name: "تلاش دوباره" }));

    expect(await screen.findByRole("heading", { name: "پرس سینه دمبل" })).toBeVisible();
  });

  it("shows an unknown exercise state with a catalog return link", async () => {
    api.getExercise.mockResolvedValue(null);
    renderDetail(
      "/exercises/unknown?body_region=upper_body&primary_muscle=chest",
    );

    expect(await screen.findByRole("heading", { name: "حرکت پیدا نشد" })).toBeVisible();
    expect(screen.getByRole("link", { name: "بازگشت به کتابخانه حرکات" })).toHaveAttribute(
      "href",
      "/exercises?body_region=upper_body&primary_muscle=chest",
    );
  });
});

describe("exercise detail content", () => {
  it("renders bilingual names, media, metadata, steps, safety notes, and navigation", async () => {
    renderDetail();

    const heading = await screen.findByRole("heading", { name: "پرس سینه دمبل" });
    expect(heading).toHaveAttribute("dir", "rtl");
    expect(screen.getByText("Dumbbell Bench Press")).toHaveAttribute("dir", "ltr");
    expect(screen.getByRole("img", { name: "نمایش حرکت پرس سینه دمبل" })).toHaveAttribute(
      "src",
      detail.media_path,
    );
    const facts = screen.getByText("عضله اصلی").closest("dl");
    expect(facts).not.toBeNull();
    expect(within(facts!).getByText("سینه")).toBeVisible();
    expect(screen.getByText("پشت بازو، سرشانه")).toBeVisible();
    expect(screen.getByText("دمبل، نیمکت")).toBeVisible();
    expect(screen.getByText("متوسط")).toBeVisible();

    const instructions = screen.getByRole("region", { name: "روش اجرای صحیح" });
    expect(within(instructions).getAllByRole("listitem")).toHaveLength(3);
    expect(within(instructions).getByText(detail.instructions_fa[0])).toBeVisible();

    const safety = screen.getByRole("region", { name: "نکات فرم و ایمنی" });
    expect(within(safety).getAllByRole("listitem")).toHaveLength(2);
    expect(within(safety).getByText(detail.safety_notes_fa[1])).toBeVisible();

    const breadcrumb = screen.getByRole("navigation", { name: "مسیر جزئیات حرکت" });
    expect(within(breadcrumb).getByRole("link", { name: "کتابخانه حرکات" })).toHaveAttribute(
      "href",
      "/exercises?body_region=upper_body&primary_muscle=chest",
    );
    expect(screen.getByRole("link", { name: "بازگشت به کتابخانه حرکات" })).toHaveAttribute(
      "href",
      "/exercises?body_region=upper_body&primary_muscle=chest",
    );
  });

  it("uses English instructions and preserves Persian name direction in English", async () => {
    await i18n.changeLanguage("en");
    renderDetail();

    expect(
      await screen.findByRole("heading", { name: "Dumbbell Bench Press" }),
    ).toHaveAttribute("dir", "ltr");
    expect(screen.getByText("پرس سینه دمبل")).toHaveAttribute("dir", "rtl");
    expect(screen.getByText(detail.instructions_en[0])).toBeVisible();
    expect(screen.queryByText(detail.instructions_fa[0])).not.toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("dir", "ltr");
  });

  it("lets the member select an available male or female media asset", async () => {
    const user = userEvent.setup();
    api.getExercise.mockResolvedValue({
      ...detail,
      media_assets: [
        {
          presentation: "male",
          role: "video",
          sort_order: 0,
          media_path: "/media/male.mp4",
          media_type: "video",
          media_source_url: null,
          media_license: "MIT",
          media_attribution: "Male creator",
        },
      ],
    });
    renderDetail();

    const selector = await screen.findByLabelText("رسانهٔ نمایش");
    await user.selectOptions(selector, "male-video-0");

    const video = screen.getByLabelText("نمایش حرکت پرس سینه دمبل");
    expect(video.tagName).toBe("VIDEO");
    expect(video).toHaveAttribute("src", "/media/male.mp4");
    expect(screen.getByText("Male creator")).toBeVisible();
  });

  it("lets the member select an unspecified owner video", async () => {
    const user = userEvent.setup();
    api.getExercise.mockResolvedValue({
      ...detail,
      media_assets: [
        {
          presentation: "unspecified",
          role: "video",
          sort_order: 0,
          media_path: "/media/owner-video.mp4",
          media_type: "video",
          media_source_url: null,
          media_license: null,
          media_attribution: "Fitsho owner-provided",
        },
      ],
    });
    renderDetail();

    const selector = await screen.findByLabelText("رسانهٔ نمایش");
    await user.selectOptions(selector, "unspecified-video-0");

    expect(screen.getByRole("option", { name: "ویدئوی مالک" })).toBeVisible();
    expect(screen.getByLabelText("نمایش حرکت پرس سینه دمبل")).toHaveAttribute(
      "src",
      "/media/owner-video.mp4",
    );
  });
});

function renderDetail(
  path = "/exercises/dumbbell-bench-press?body_region=upper_body&primary_muscle=chest",
) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/exercises/:slug" element={<ExerciseDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}
