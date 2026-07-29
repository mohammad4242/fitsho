import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import type {
  ExerciseCategories,
  ExerciseSummary,
  PaginatedExercises,
} from "./types";

const api = vi.hoisted(() => ({
  getExerciseCategories: vi.fn(),
  getExercises: vi.fn(),
}));

vi.mock("./api", () => api);
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
    { value: "calves", name_en: "Calves", name_fa: "ساق" },
  ],
  core: [
    { value: "abs", name_en: "Abs", name_fa: "شکم" },
    { value: "obliques", name_en: "Obliques", name_fa: "پهلو" },
    { value: "lower_back", name_en: "Lower Back", name_fa: "فیله" },
  ],
};

const benchPress: ExerciseSummary = {
  id: "018f0000-0000-7000-8000-000000000001",
  slug: "dumbbell-bench-press",
  name_en: "Dumbbell Bench Press",
  name_fa: "پرس سینه دمبل",
  body_region: "upper_body",
  primary_muscle: "chest",
  secondary_muscles: ["triceps", "shoulders"],
  equipment: ["dumbbell", "bench"],
  difficulty: "intermediate",
  media_path: "/exercises/upper-body/chest/dumbbell-bench-press.gif",
  media_type: "gif",
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
  api.getExerciseCategories.mockResolvedValue(categories);
  api.getExercises.mockResolvedValue(populatedPage);
  await i18n.changeLanguage("fa");
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("catalog selection flow", () => {
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
    renderCatalog("/exercises?body_region=core&primary_muscle=lower_back");

    expect(
      await screen.findByText("هنوز حرکتی برای این گروه عضلانی اضافه نشده است."),
    ).toBeVisible();

    await user.selectOptions(
      screen.getByRole("combobox", { name: "تجهیزات" }),
      "dumbbell",
    );

    expect(await screen.findByText("حرکتی با این فیلترها پیدا نشد.")).toBeVisible();
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
