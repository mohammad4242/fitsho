import re

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx", "r") as f:
    content = f.read()

with open("/tmp/selectExercise.txt", "r") as f:
    old_select_exercise = f.read()

new_select_exercise = """  function selectExercise(exercise: AdminExercise) {
    if (pickerTarget === null) return;
    const { dayIndex, slotIndex, member } = pickerTarget;
    const muscles: MuscleGroup[] = exercise.primary_muscle === null
      ? exercise.secondary_muscles.slice(0, 1)
      : [exercise.primary_muscle, ...exercise.secondary_muscles];
    const targetMuscles: MuscleGroup[] = muscles.length > 0 ? muscles : ["chest"];

    if (member === "primary") {
      patchSlot(dayIndex, slotIndex, {
        exercise_id: exercise.id,
        exercise_name_fa: exercise.name_fa,
        exercise_name_en: exercise.name_en,
        exercise_slug: exercise.slug,
        movement_pattern: exercise.movement_pattern,
        target_muscles: targetMuscles,
      });
    } else {
      patchSlot(dayIndex, slotIndex, {
        superset_exercise_id: exercise.id,
        superset_exercise_name_fa: exercise.name_fa,
        superset_exercise_name_en: exercise.name_en,
        superset_exercise_slug: exercise.slug,
      });
    }
    setPickerTarget(null);
  }
  
  function addDraftSlot(dayIndex: number) {
    const existingSlotCount = form.days[dayIndex]?.slots.length ?? 0;
    const slot: AdminTrainingTemplateSlotForm = {
      exercise_id: null,
      exercise_name_fa: null,
      exercise_name_en: null,
      exercise_slug: null,
      superset_exercise_id: null,
      superset_exercise_name_fa: null,
      superset_exercise_name_en: null,
      superset_exercise_slug: null,
      display_name_en: null,
      display_name_fa: null,
      target_muscles: ["chest"],
      movement_pattern: "other",
      intensity_method: "standard",
      adaptation_priority: "core",
      superset_group: null,
      sets: 3,
      rep_min: 8,
      rep_max: 12,
      target_rir: 2,
      rest_seconds: 90,
    };
    const newSlotKey = `${dayIndex}-${existingSlotCount}`;
    setForm((current) => ({
      ...current,
      days: current.days.map((day, index) => (
        index === dayIndex ? { ...day, slots: [...day.slots, slot as any] } : day
      )),
    }));
    setExpandedDays((current) => new Set([...current, dayIndex]));
    setExpandedSlots((current) => new Set([...current, newSlotKey]));
  }"""

content = content.replace(old_select_exercise, new_select_exercise)

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx", "w") as f:
    f.write(content)

