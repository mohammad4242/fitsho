import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import type {
  ExerciseCategories,
  ExerciseSummary,
  PaginatedExercises,
} from "./types";
import { muscleGroups } from "./types";

const api = vi.hoisted(() => ({
  getExerciseCategories: vi.fn(),
  getExercises: vi.fn(),
}));
const adminApi = vi.hoisted(() => ({
  getAdminExercises: vi.fn(),
  deleteAdminExercise: vi.fn(),
}));
const auth = vi.hoisted(() => ({ isAdmin: false }));

vi.mock("./api", () => api);
vi.mock("../admin/api", () => adminApi);
vi.mock("../auth/AuthContext", () => ({
  useAuth: () => ({ user: { is_admin: auth.isAdmin } }),
}));
vi.mock("../../shared/AuthenticatedHeader", () => ({
  AuthenticatedHeader: () => null,
}));

import { ExerciseCatalogPage } from "./ExerciseCatalogPage";

const categories: ExerciseCategories = {
  body_regions: [
    { value: "upper_body", name_en: "Upper Body", name_fa: "بالاتنه" },
    { value: "lower_body", name_en: "Lower Body", name_fa: "پایین‌تنه" },
    { value: "core", name_en: "Core", name_fa: "میان‌تنه" },
  ],
  upper_body: [
    { value: "chest", name_en: "Chest", name_fa: "سینه" },
    { value: "back", name_en: "Back", name_fa: "پشت و زیر بغل" },
    { value: "shoulders", name_en: "Shoulders", name_fa: "سرشانه" },
    { value: "biceps", name_en: "Biceps", name_fa: "جلو بازو" },
    { value: "triceps", name_en: "Triceps", name_fa: "پشت بازو" },
    { value: "traps", name_en: "Traps", name_fa: "کول" },
  ],
  lower_body: [
    { value: "glutes", name_en: "Glutes", name_fa: "باسن" },
    { value: "quadriceps", name_en: "Quadriceps", name_fa: "جلو پا" },
    { value: "hamstrings", name_en: "Hamstrings", name_fa: "پشت پا" },
    { value: "adductors", name_en: "Adductors", name_fa: "داخل پا" },
    { value: "abductors", name_en: "Abductors", name_fa: "بیرون پا" },
    { value: "legs", name_en: "Legs", name_fa: "کل پا" },
    { value: "calves", name_en: "Calves", name_fa: "ساق" },
  ],
  core: [
    { value: "abs", name_en: "Abs", name_fa: "شکم" },
    { value: "obliques", name_en: "Obliques", name_fa: "پهلو" },
  ],
  muscle_focuses: Object.fromEntries(muscleGroups.map((muscle) => [
    muscle,
    muscle === "chest"
      ? [
          { value: "general_chest", name_en: "General Chest", name_fa: "کل سینه" },
          { value: "upper_chest", name_en: "Upper Chest", name_fa: "بالاسینه" },
          { value: "mid_chest", name_en: "Mid Chest", name_fa: "میان‌سینه" },
          { value: "lower_chest", name_en: "Lower Chest", name_fa: "زیرسینه" },
        ]
      : muscle === "back"
        ? [
            { value: "general_back", name_en: "General Back", name_fa: "کل پشت" },
            { value: "lats", name_en: "Lats", name_fa: "زیر بغل" },
            { value: "lower_back", name_en: "Lower Back", name_fa: "پایین پشت" },
            { value: "mid_back_rhomboids", name_en: "Mid Back / Rhomboids", name_fa: "میانه پشت / رومبوئید" },
            { value: "upper_back", name_en: "Upper Back", name_fa: "بالای پشت" },
          ]
      : [],
  ])) as unknown as ExerciseCategories["muscle_focuses"],
};

const benchPress: ExerciseSummary = {
  id: "018f0000-0000-7000-8000-000000000001",
  slug: "dumbbell-bench-press",
  name_en: "Dumbbell Bench Press",
  name_fa: "پرس سینه دمبل",
  body_region: "upper_body",
  primary_muscle: "chest",
  muscle_focus: "mid_chest",
  labels: [],
  secondary_muscles: ["triceps", "shoulders"],
  equipment: ["dumbbell", "bench"],
  difficulty: "intermediate",
  media_path: "/exercises/upper-body/chest/dumbbell-bench-press.gif",
  media_type: "gif",
  content_type: "exercise",
};

const populatedPage: PaginatedExercises = {
  items: [benchPress],
  page: 1,
  page_size: 12,
  total: 1,
  total_pages: 1,
};

const emptyPage: PaginatedExercises = {
  items: [],
  page: 1,
  page_size: 12,
  total: 0,
  total_pages: 0,
};

beforeEach(async () => {
  api.getExerciseCategories.mockReset();
  api.getExercises.mockReset();
  adminApi.getAdminExercises.mockReset();
  adminApi.deleteAdminExercise.mockReset();
  auth.isAdmin = false;
  api.getExerciseCategories.mockResolvedValue(categories);
  api.getExercises.mockResolvedValue(populatedPage);
  adminApi.getAdminExercises.mockResolvedValue({
    ...populatedPage,
    items: [{ ...benchPress, is_active: false, needs_review: true }],
  });
  await i18n.changeLanguage("fa");
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("catalog selection flow", () => {
  it("uses the supplied strength still in the catalog header", async () => {
    renderCatalog();

    const background = await screen.findByTestId("member-header-image");
    expect(background).toHaveAttribute(
      "src",
      expect.stringContaining("hero-strength-fallback"),
    );
    expect(background.parentElement).toHaveClass("member-page-background");
  });

  it("moves from regions to muscles and then renders a bilingual exercise card", async () => {
    const user = userEvent.setup();
    renderCatalog();

    expect(
      await screen.findByRole("heading", { name: "کتابخانه حرکات" }),
    ).toHaveClass("fitsho-display");
    expect(screen.getByRole("button", { name: /بالاتنه.*Upper Body/ })).toBeVisible();
    expect(screen.getByRole("button", { name: /پایین‌تنه.*Lower Body/ })).toBeVisible();
    expect(screen.getByRole("button", { name: /میان‌تنه.*Core/ })).toBeVisible();
    expect(screen.queryByRole("button", { name: /سینه.*Chest/ })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /بالاتنه.*Upper Body/ }));

    expect(locationValue()).toBe("/exercises?body_region=upper_body");
    expect(screen.getByRole("button", { name: /سینه.*Chest/ })).toBeVisible();
    expect(screen.getByRole("button", { name: /کول.*Traps/ })).toBeVisible();
    expect(screen.queryByText("پرس سینه دمبل")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /سینه.*Chest/ }));

    const card = await screen.findByRole("article", { name: "پرس سینه دمبل" });
    expect(within(card).getByText("پرس سینه دمبل")).toHaveAttribute("dir", "rtl");
    expect(within(card).getByText("Dumbbell Bench Press")).toHaveAttribute("dir", "ltr");
    expect(within(card).getByText("سینه")).toBeVisible();
    expect(within(card).getByText("دمبل، نیمکت")).toBeVisible();
    expect(within(card).getByText("متوسط")).toBeVisible();
    expect(within(card).getByRole("img", { name: "نمایش حرکت پرس سینه دمبل" })).toBeVisible();
    expect(within(card).getByRole("link", { name: "مشاهده حرکت" })).toHaveAttribute(
      "href",
      "/exercises/dumbbell-bench-press?body_region=upper_body&primary_muscle=chest",
    );
  });

  it("shows abductors and legs as separate lower-body groups", async () => {
    const user = userEvent.setup();
    renderCatalog();

    await user.click(await screen.findByRole("button", { name: /پایین‌تنه.*Lower Body/ }));

    expect(screen.getByRole("button", { name: /بیرون پا.*Abductors/ })).toBeVisible();
    expect(screen.getByRole("button", { name: /کل پا.*Legs/ })).toBeVisible();
  });

  it("uses breadcrumb actions to change the current catalog level", async () => {
    const user = userEvent.setup();
    renderCatalog("/exercises?body_region=upper_body&primary_muscle=chest");

    const breadcrumb = await screen.findByRole("navigation", {
      name: "مسیر کتابخانه حرکات",
    });
    await user.click(within(breadcrumb).getByRole("button", { name: "بالاتنه" }));
    expect(locationValue()).toBe("/exercises?body_region=upper_body");

    await user.click(within(breadcrumb).getByRole("button", { name: "کتابخانه حرکات" }));
    expect(locationValue()).toBe("/exercises");
  });

  it("keeps All backward-compatible and filters by a selected muscle focus", async () => {
    const user = userEvent.setup();
    renderCatalog("/exercises?body_region=upper_body&primary_muscle=chest");

    expect(await screen.findByRole("button", { name: "همه حرکات سینه" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(api.getExercises).toHaveBeenLastCalledWith(
      expect.objectContaining({ primary_muscle: "chest", muscle_focus: undefined }),
    );

    await user.click(screen.getByRole("button", { name: /بالاسینه.*Upper Chest/ }));

    expect(locationValue()).toBe(
      "/exercises?body_region=upper_body&primary_muscle=chest&muscle_focus=upper_chest",
    );
    expect(api.getExercises).toHaveBeenLastCalledWith(
      expect.objectContaining({ primary_muscle: "chest", muscle_focus: "upper_chest" }),
    );
  });

  it("supports keyboard selection for regions and muscles", async () => {
    const user = userEvent.setup();
    renderCatalog();

    const upperBody = await screen.findByRole("button", { name: /بالاتنه.*Upper Body/ });
    upperBody.focus();
    await user.keyboard("{Enter}");

    const chest = screen.getByRole("button", { name: /سینه.*Chest/ });
    chest.focus();
    await user.keyboard(" ");

    expect(await screen.findByRole("article", { name: "پرس سینه دمبل" })).toBeVisible();
  });

  it("reorders bilingual names and directions in English", async () => {
    await i18n.changeLanguage("en");
    const user = userEvent.setup();
    renderCatalog();

    await user.click(await screen.findByRole("button", { name: /Upper Body.*بالاتنه/ }));
    await user.click(screen.getByRole("button", { name: /Chest.*سینه/ }));

    const card = await screen.findByRole("article", { name: "Dumbbell Bench Press" });
    expect(within(card).getByText("Dumbbell Bench Press")).toHaveAttribute("dir", "ltr");
    expect(within(card).getByText("پرس سینه دمبل")).toHaveAttribute("dir", "rtl");
    expect(document.documentElement).toHaveAttribute("dir", "ltr");
  });
});

describe("catalog filters and states", () => {
  it("shows only guides in the simple guide view for the selected muscle", async () => {
    const user = userEvent.setup();
    const guide = { ...benchPress, slug: "bench-angle-guide", name_fa: "راهنمای زاویه پرس", content_type: "guide" as const };
    api.getExercises.mockImplementation(async (filters) =>
      filters.content_type === "guide"
        ? { ...populatedPage, items: [guide] }
        : populatedPage,
    );
    renderCatalog("/exercises?body_region=upper_body&primary_muscle=chest");

    await screen.findByRole("button", { name: "همه حرکات سینه" });
    expect(api.getExercises).toHaveBeenLastCalledWith(
      expect.objectContaining({ content_type: "exercise" }),
    );
    await user.click(await screen.findByRole("button", { name: "راهنما" }));

    expect(locationValue()).toBe(
      "/exercises?body_region=upper_body&primary_muscle=chest&content_type=guide",
    );
    expect(api.getExercises).toHaveBeenLastCalledWith(
      expect.objectContaining({ content_type: "guide", muscle_focus: undefined }),
    );
    expect(screen.queryByRole("button", { name: "همه حرکات سینه" })).not.toBeInTheDocument();
    expect(await screen.findByRole("article", { name: "راهنمای زاویه پرس" })).toBeVisible();
  });

  it("opens the cardio catalog section", async () => {
    const user = userEvent.setup();
    renderCatalog();

    await user.click(await screen.findByRole("button", { name: "هوازی" }));

    expect(locationValue()).toBe("/exercises?labels=cardio");
    expect(api.getExercises).toHaveBeenLastCalledWith(
      expect.objectContaining({ labels: ["cardio"] }),
    );
  });

  it("writes accessible filters to the URL and resets pagination", async () => {
    const user = userEvent.setup();
    renderCatalog(
      "/exercises?body_region=upper_body&primary_muscle=chest&page=3",
    );

    const equipment = await screen.findByRole("combobox", { name: "تجهیزات" });
    await user.selectOptions(equipment, "dumbbell");
    expect(locationValue()).toBe(
      "/exercises?body_region=upper_body&primary_muscle=chest&equipment=dumbbell",
    );

    await user.selectOptions(screen.getByRole("combobox", { name: "سطح سختی" }), "beginner");
    await user.type(screen.getByRole("searchbox", { name: "جستجوی حرکت" }), "press");

    expect(locationValue()).toBe(
      "/exercises?body_region=upper_body&primary_muscle=chest&equipment=dumbbell&difficulty=beginner&search=press",
    );
  });

  it("moves between result pages without losing filters", async () => {
    const user = userEvent.setup();
    api.getExercises.mockResolvedValue({
      ...populatedPage,
      total: 25,
      total_pages: 3,
    });
    renderCatalog(
      "/exercises?body_region=upper_body&primary_muscle=chest&equipment=dumbbell",
    );

    await user.click(await screen.findByRole("button", { name: "صفحه بعد" }));

    expect(locationValue()).toBe(
      "/exercises?body_region=upper_body&primary_muscle=chest&equipment=dumbbell&page=2",
    );
  });

  it("shows loading while selected exercises are requested", async () => {
    const pending = deferred<PaginatedExercises>();
    api.getExercises.mockReturnValue(pending.promise);
    renderCatalog("/exercises?body_region=upper_body&primary_muscle=chest");

    const loadingMessage = await screen.findByText("در حال دریافت حرکات…");
    expect(loadingMessage.closest('[role="status"]')).toBeInTheDocument();

    pending.resolve(populatedPage);
    expect(await screen.findByRole("article", { name: "پرس سینه دمبل" })).toBeVisible();
  });

  it("retries a failed exercise request without changing filters", async () => {
    const user = userEvent.setup();
    api.getExercises
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(populatedPage);
    renderCatalog(
      "/exercises?body_region=upper_body&primary_muscle=chest&equipment=dumbbell",
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "حرکات دریافت نشدند",
    );
    await user.click(screen.getByRole("button", { name: "تلاش دوباره" }));

    expect(await screen.findByRole("article", { name: "پرس سینه دمبل" })).toBeVisible();
    expect(locationValue()).toBe(
      "/exercises?body_region=upper_body&primary_muscle=chest&equipment=dumbbell",
    );
  });

  it("distinguishes an empty muscle group from filters with no matches", async () => {
    const user = userEvent.setup();
    api.getExercises.mockResolvedValue(emptyPage);
    renderCatalog("/exercises?body_region=upper_body&primary_muscle=back");

    expect(
      await screen.findByText("هنوز حرکتی برای این گروه عضلانی اضافه نشده است."),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: /پایین پشت/ }));

    await user.selectOptions(
      screen.getByRole("combobox", { name: "تجهیزات" }),
      "dumbbell",
    );

    expect(await screen.findByText("حرکتی با این فیلترها پیدا نشد.")).toBeVisible();
  });
});

describe("administrator controls", () => {
  it("keeps all administration controls hidden from members", async () => {
    renderCatalog("/exercises?body_region=upper_body&primary_muscle=chest");

    const card = await screen.findByRole("article", { name: "پرس سینه دمبل" });
    expect(screen.queryByRole("link", { name: "افزودن حرکت" })).not.toBeInTheDocument();
    expect(within(card).queryByRole("link", { name: "ویرایش" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "وضعیت مدیریتی" })).not.toBeInTheDocument();
  });

  it("links add and edit actions back to the current library context", async () => {
    auth.isAdmin = true;
    renderCatalog(
      "/exercises?body_region=upper_body&primary_muscle=chest&muscle_focus=mid_chest&equipment=dumbbell&search=press",
    );

    const card = await screen.findByRole("article", { name: "پرس سینه دمبل" });
    const returnTo = encodeURIComponent(
      "/exercises?body_region=upper_body&primary_muscle=chest&muscle_focus=mid_chest&equipment=dumbbell&search=press",
    );
    expect(screen.getByRole("link", { name: "افزودن حرکت" })).toHaveAttribute(
      "href",
      `/admin/exercises/new?body_region=upper_body&primary_muscle=chest&muscle_focus=mid_chest&return_to=${returnTo}`,
    );
    expect(within(card).getByRole("link", { name: "ویرایش" })).toHaveAttribute(
      "href",
      `/admin/exercises/${benchPress.id}/edit?return_to=${returnTo}`,
    );
  });

  it("confirms and removes an exercise through the admin delete action", async () => {
    auth.isAdmin = true;
    const user = userEvent.setup();
    adminApi.deleteAdminExercise.mockResolvedValue(undefined);
    renderCatalog("/exercises?body_region=upper_body&primary_muscle=chest");

    const card = await screen.findByRole("article", { name: "پرس سینه دمبل" });
    await user.click(within(card).getByRole("button", { name: "حذف" }));

    const dialog = screen.getByRole("dialog", { name: "حذف حرکت" });
    expect(dialog).toHaveTextContent("پرس سینه دمبل");
    expect(adminApi.deleteAdminExercise).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "حذف قطعی" }));

    await waitFor(() => expect(adminApi.deleteAdminExercise).toHaveBeenCalledWith(benchPress.id));
    expect(screen.queryByRole("article", { name: "پرس سینه دمبل" })).not.toBeInTheDocument();
  });

  it("shows a safe error when the exercise cannot be deleted", async () => {
    auth.isAdmin = true;
    const user = userEvent.setup();
    adminApi.deleteAdminExercise.mockRejectedValue(new Error("Request failed"));
    renderCatalog("/exercises?body_region=upper_body&primary_muscle=chest");

    const card = await screen.findByRole("article", { name: "پرس سینه دمبل" });
    await user.click(within(card).getByRole("button", { name: "حذف" }));
    await user.click(
      within(screen.getByRole("dialog", { name: "حذف حرکت" })).getByRole("button", {
        name: "حذف قطعی",
      }),
    );

    expect(await within(screen.getByRole("dialog", { name: "حذف حرکت" })).findByRole("alert")).toHaveTextContent(
      "حرکت حذف نشد. دوباره تلاش کنید.",
    );
    expect(screen.getByRole("article", { name: "پرس سینه دمبل" })).toBeInTheDocument();
  });

  it("uses the protected admin list only for explicit admin status filters", async () => {
    auth.isAdmin = true;
    const user = userEvent.setup();
    renderCatalog(
      "/exercises?body_region=upper_body&primary_muscle=chest&equipment=dumbbell&difficulty=intermediate&search=press",
    );

    await screen.findByRole("article", { name: "پرس سینه دمبل" });
    expect(api.getExercises).toHaveBeenCalled();
    expect(adminApi.getAdminExercises).not.toHaveBeenCalled();

    await user.selectOptions(
      screen.getByRole("combobox", { name: "وضعیت مدیریتی" }),
      "inactive",
    );

    expect(
      within(await screen.findByRole("article", { name: "پرس سینه دمبل" })).getByText("غیرفعال"),
    ).toBeVisible();
    expect(adminApi.getAdminExercises).toHaveBeenLastCalledWith(expect.objectContaining({
      body_region: "upper_body",
      primary_muscle: "chest",
      equipment: "dumbbell",
      difficulty: "intermediate",
      search: "press",
      is_active: false,
      page: 1,
      content_type: "exercise",
    }));
    expect(locationValue()).toContain("admin_status=inactive");
  });
});

function renderCatalog(path = "/exercises") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <ExerciseCatalogPage />
      <LocationProbe />
    </MemoryRouter>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
}

function locationValue(): string {
  return screen.getByTestId("location").textContent ?? "";
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
