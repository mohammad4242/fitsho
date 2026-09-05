import re

with open("/tmp/editor.tsx", "r") as f:
    content = f.read()

# 1. Update PickerTarget
old_picker_target = """type PickerTarget = {
  dayIndex: number;
  slotIndex: number | null;
};"""
new_picker_target = """type PickerTarget = {
  dayIndex: number;
  slotIndex: number;
  member: "primary" | "superset";
};"""
content = content.replace(old_picker_target, new_picker_target)

# 2. Update AdminTrainingTemplateSlotForm
old_slot_form = """type AdminTrainingTemplateSlotForm = AdminTrainingTemplateSlotWrite & {
  exercise_name_fa: string | null;
  exercise_name_en: string | null;
  exercise_slug: string | null;
};"""
new_slot_form = """type AdminTrainingTemplateSlotForm = Omit<AdminTrainingTemplateSlotWrite, "exercise_id"> & {
  exercise_id: string | null;
  exercise_name_fa: string | null;
  exercise_name_en: string | null;
  exercise_slug: string | null;
  superset_exercise_id: string | null;
  superset_exercise_name_fa: string | null;
  superset_exercise_name_en: string | null;
  superset_exercise_slug: string | null;
};"""
content = content.replace(old_slot_form, new_slot_form)

# 3. Update templateToForm and formToPayload mapping
# Wait, let's use regex for templateToForm mapping

content = re.sub(
    r'slots: day\.slots\.filter\(\(slot\) => slot\.exercise !== null\)\.map\(\(slot\) => \(\{[\s\S]*?\}\)\),',
    """slots: day.slots.map((slot) => ({
        exercise_id: slot.exercise?.id ?? null,
        exercise_name_en: slot.exercise?.name_en ?? null,
        exercise_name_fa: slot.exercise?.name_fa ?? null,
        exercise_slug: slot.exercise?.slug ?? null,
        superset_exercise_id: slot.superset_exercise?.id ?? null,
        superset_exercise_name_en: slot.superset_exercise?.name_en ?? null,
        superset_exercise_name_fa: slot.superset_exercise?.name_fa ?? null,
        superset_exercise_slug: slot.superset_exercise?.slug ?? null,
        display_name_en: slot.placeholder_name_en,
        display_name_fa: slot.placeholder_name_fa,
        target_muscles: slot.target_muscles,
        movement_pattern: slot.movement_pattern,
        intensity_method: slot.intensity_method,
        adaptation_priority: slot.adaptation_priority,
        superset_group: slot.superset_group,
        sets: slot.sets,
        rep_min: slot.rep_min,
        rep_max: slot.rep_max,
        target_rir: slot.target_rir,
        rest_seconds: slot.rest_seconds,
      })),""",
    content
)

content = re.sub(
    r'slots: day\.slots\.map\(\(slot\) => \(\{[^\}]*?exercise_id: slot\.exercise_id,[^\}]*?\}\)\),',
    """slots: day.slots.filter((slot) => slot.exercise_id !== null).map((slot) => ({
        exercise_id: slot.exercise_id!,
        superset_exercise_id: slot.superset_exercise_id,
        display_name_en: slot.display_name_en?.trim() ? slot.display_name_en.trim() : null,
        display_name_fa: slot.display_name_fa?.trim() ? slot.display_name_fa.trim() : null,
        target_muscles: slot.target_muscles,
        movement_pattern: slot.movement_pattern,
        intensity_method: slot.intensity_method,
        adaptation_priority: slot.adaptation_priority,
        superset_group: slot.superset_group,
        sets: slot.sets,
        rep_min: slot.rep_min,
        rep_max: slot.rep_max,
        target_rir: slot.target_rir,
        rest_seconds: slot.rest_seconds,
      })),""",
    content
)

# 4. update selectExercise
old_select_exercise = """  function selectExercise(exercise: AdminExercise) {
    if (pickerTarget === null) return;
    const { dayIndex, slotIndex } = pickerTarget;
    const muscles: MuscleGroup[] = exercise.primary_muscle === null
      ? exercise.secondary_muscles.slice(0, 1)
      : [exercise.primary_muscle, ...exercise.secondary_muscles];
    const targetMuscles: MuscleGroup[] = muscles.length > 0 ? muscles : ["chest"];

    if (slotIndex !== null) {
      // Replace exercise in existing slot, retaining workout-specific settings
      patchSlot(dayIndex, slotIndex, {
        exercise_id: exercise.id,
        exercise_name_fa: exercise.name_fa,
        exercise_name_en: exercise.name_en,
        exercise_slug: exercise.slug,
        movement_pattern: exercise.movement_pattern,
        target_muscles: targetMuscles,
      });
    } else {
      // Add new slot to day
      const existingSlotCount = form.days[dayIndex]?.slots.length ?? 0;
      patchDay(dayIndex, {
        slots: [
          ...(form.days[dayIndex]?.slots ?? []),
          {
            exercise_id: exercise.id,
            exercise_name_fa: exercise.name_fa,
            exercise_name_en: exercise.name_en,
            exercise_slug: exercise.slug,
            display_name_en: null,
            display_name_fa: null,
            target_muscles: targetMuscles,
            movement_pattern: exercise.movement_pattern,
            intensity_method: "standard",
            adaptation_priority: "accessory",
            superset_group: null,
            sets: 3,
            rep_min: 8,
            rep_max: 15,
            target_rir: 2,
            rest_seconds: 90,
          },
        ],
      });
      const newSlotKey = `${dayIndex}-${existingSlotCount}`;
      setExpandedSlots((current) => new Set([...current, newSlotKey]));
    }
    setPickerTarget(null);
  }"""

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
    patchDay(dayIndex, {
      slots: [
        ...(form.days[dayIndex]?.slots ?? []),
        {
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
          adaptation_priority: "accessory",
          superset_group: null,
          sets: 3,
          rep_min: 8,
          rep_max: 15,
          target_rir: 2,
          rest_seconds: 90,
        },
      ],
    });
    const newSlotKey = `${dayIndex}-${existingSlotCount}`;
    setExpandedSlots((current) => new Set([...current, newSlotKey]));
  }"""
content = content.replace(old_select_exercise, new_select_exercise)

# 5. Fix Save validation
old_save_val = """    if (slotCountProblems) {
      setSaveError(t("admin.templateEditor.slotCountError"));
      return;
    }"""
new_save_val = """    if (slotCountProblems) {
      setSaveError(t("admin.templateEditor.slotCountError"));
      return;
    }
    for (const day of form.days) {
      for (const slot of day.slots) {
        if (!slot.exercise_id) {
          setSaveError("Movement 1 is required for all slots.");
          return;
        }
        if (slot.intensity_method === "superset" && !slot.superset_exercise_id) {
          setSaveError("Movement 2 is required for Superset slots.");
          return;
        }
        if (slot.intensity_method === "superset" && slot.exercise_id === slot.superset_exercise_id) {
          setSaveError("Superset movements must be different.");
          return;
        }
      }
    }"""
content = content.replace(old_save_val, new_save_val)

with open("/tmp/editor_step1.tsx", "w") as f:
    f.write(content)
