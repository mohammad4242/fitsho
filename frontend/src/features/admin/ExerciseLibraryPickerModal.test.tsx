import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const exercisesApi = vi.hoisted(() => ({
  getExerciseCategories: vi.fn(),
}));

const adminApi = vi.hoisted(() => ({
  getAdminExercises: vi.fn(),
}));

vi.mock("../exercises/api", () => exercisesApi);
vi.mock("./api", () => adminApi);

import { ExerciseLibraryPickerModal } from "./ExerciseLibraryPickerModal";
import type { AdminExercise } from "./types";

const mockCategories = {
  body_regions: [
    { value: "upper_body", name_en: "Upper Body", name_fa: "بالاتنه" },
    { value: "lower_body", name_en: "Lower Body", name_fa: "پایین‌تنه" },
    { value: "core", name_en: "Core", name_fa: "میان‌تنه" },
  ],
  upper_body: [
    { value: "chest", name_en: "Chest", name_fa: "سینه" },
    { value: "back", name_en: "Back", name_fa: "پشت" },
  ],
  lower_body: [
    { value: "quadriceps", name_en: "Quadriceps", name_fa: "چهارسر" },
  ],
  core: [
    { value: "abs", name_en: "Abs", name_fa: "شکم" },
  ],
  muscle_focuses: {
    chest: [
      { value: "upper_chest", name_en: "Upper Chest", name_fa: "بالاسینه" },
      { value: "mid_chest", name_en: "Mid Chest", name_fa: "میانسینه" },
    ],
    quadriceps: [],
  },
};

const mockBenchPress: AdminExercise = {
  id: "ex-1",
  slug: "incline-dumbbell-bench-press",
  name_en: "Incline Dumbbell Bench Press",
  name_fa: "پرس بالا سینه دمبل",
  content_type: "exercise",
  body_region: "upper_body",
  primary_muscle: "chest",
  muscle_focus: "upper_chest",
  secondary_muscles: ["triceps"],
  equipment: ["dumbbell", "bench"],
  difficulty: "intermediate",
  movement_pattern: "horizontal_push",
  exercise_type: "compound",
  caution_tags: [],
  labels: [],
  instructions_en: ["Lie on bench", "Press weights up", "Lower with control"],
  instructions_fa: ["روی میز دراز بکشید", "وزنه‌ها را بالا ببرید", "با کنترل پایین بیاورید"],
  safety_notes_en: [],
  safety_notes_fa: [],
  source: null,
  source_id: null,
  aliases_en: [],
  short_description_en: null,
  steps_en: [],
  form_cues_en: [],
  common_mistakes_en: [],
  breathing_en: null,
  needs_review: false,
  is_active: true,
  is_programmable: true,
  body_position: "lying",
  stability_demand: "moderate",
  skill_demand: "moderate",
  impact_level: "low",
  axial_loading_level: "low",
  fatigue_cost: 3,
  setup_cost: 2,
  laterality: "bilateral",
  substitution_group: "chest_press",
  range_of_motion_profile: null,
  media_path: "/media/ex1.webp",
  media_type: "animated_webp",
  media_source_url: null,
  media_license: null,
  media_attribution: null,
  created_at: "2026-07-27T00:00:00Z" as unknown as Date,
  updated_at: "2026-07-27T00:00:00Z" as unknown as Date,
};

describe("ExerciseLibraryPickerModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    exercisesApi.getExerciseCategories.mockResolvedValue(mockCategories);
    adminApi.getAdminExercises.mockResolvedValue({
      items: [mockBenchPress],
      page: 1,
      page_size: 50,
      total: 1,
      total_pages: 1,
    });
  });

  it("navigates through hierarchy: region -> muscle -> focus -> exercise list and selects exercise", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const onClose = vi.fn();

    render(
      <ExerciseLibraryPickerModal
        isOpen={true}
        onClose={onClose}
        onSelect={onSelect}
      />,
    );

    // Stage 1: Regions
    expect(await screen.findByRole("button", { name: /بالاتنه/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /پایین‌تنه/ })).toBeInTheDocument();

    // Click Upper Body -> Stage 2: Muscles
    await user.click(screen.getByRole("button", { name: /بالاتنه/ }));
    expect(await screen.findByRole("button", { name: /سینه/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /پشت/ })).toBeInTheDocument();

    // Click Chest -> Stage 3: Muscle Focuses
    await user.click(screen.getByRole("button", { name: /سینه/ }));
    expect(await screen.findByRole("button", { name: /بالاسینه/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /همه حرکات این عضله/ })).toBeInTheDocument();

    // Click Upper Chest -> Stage 4: Exercises
    await user.click(screen.getByRole("button", { name: /بالاسینه/ }));

    expect(adminApi.getAdminExercises).toHaveBeenCalledWith(
      expect.objectContaining({
        body_region: "upper_body",
        primary_muscle: "chest",
        muscle_focus: "upper_chest",
      }),
    );

    const exerciseItem = await screen.findByRole("button", { name: /پرس بالا سینه دمبل/ });
    expect(exerciseItem).toBeInTheDocument();

    // Select Exercise
    await user.click(exerciseItem);
    expect(onSelect).toHaveBeenCalledWith(mockBenchPress);
  });

  it("skips focus stage when muscle has no focus subdivisions", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const onClose = vi.fn();

    render(
      <ExerciseLibraryPickerModal
        isOpen={true}
        onClose={onClose}
        onSelect={onSelect}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /پایین‌تنه/ }));
    await user.click(await screen.findByRole("button", { name: /چهارسر/ }));

    // Directly queries exercises for quadriceps
    expect(adminApi.getAdminExercises).toHaveBeenCalledWith(
      expect.objectContaining({
        body_region: "lower_body",
        primary_muscle: "quadriceps",
      }),
    );
  });

  it("searches exercises directly bypassing hierarchical navigation", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const onClose = vi.fn();

    render(
      <ExerciseLibraryPickerModal
        isOpen={true}
        onClose={onClose}
        onSelect={onSelect}
      />,
    );

    const searchInput = await screen.findByPlaceholderText(/جست‌وجو با نام فارسی یا انگلیسی/);
    await user.type(searchInput, "bench");

    await waitFor(() => {
      expect(adminApi.getAdminExercises).toHaveBeenCalledWith(
        expect.objectContaining({
          search: "bench",
          is_active: true,
        }),
      );
    });

    const exerciseItem = await screen.findByRole("button", { name: /پرس بالا سینه دمبل/ });
    expect(exerciseItem).toBeInTheDocument();
    await user.click(exerciseItem);
    expect(onSelect).toHaveBeenCalledWith(mockBenchPress);
  });

  it("handles back button and breadcrumb clicks", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const onClose = vi.fn();

    render(
      <ExerciseLibraryPickerModal
        isOpen={true}
        onClose={onClose}
        onSelect={onSelect}
      />,
    );

    await user.click(await screen.findByRole("button", { name: /بالاتنه/ }));
    await user.click(await screen.findByRole("button", { name: /سینه/ }));

    // Breadcrumb has "کتابخانه", "بالاتنه"
    expect(screen.getByRole("button", { name: "کتابخانه" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "بالاتنه" })).toBeInTheDocument();

    // Click back button
    await user.click(screen.getByRole("button", { name: /بازگشت/ }));
    expect(screen.getByRole("button", { name: /سینه/ })).toBeInTheDocument();

    // Click breadcrumb "کتابخانه" to return to root
    await user.click(screen.getByRole("button", { name: "کتابخانه" }));
    expect(screen.getByRole("button", { name: /بالاتنه/ })).toBeInTheDocument();
  });

  it("closes when close button is clicked or Escape is pressed", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const onClose = vi.fn();

    render(
      <ExerciseLibraryPickerModal
        isOpen={true}
        onClose={onClose}
        onSelect={onSelect}
      />,
    );

    await user.click(await screen.findByRole("button", { name: "بستن" }));
    expect(onClose).toHaveBeenCalled();

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
