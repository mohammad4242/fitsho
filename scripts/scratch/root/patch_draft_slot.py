import re

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx", "r") as f:
    content = f.read()

# 1. Insert addDraftSlot right before `async function save()`
draft_slot_fn = """  function addDraftSlot(dayIndex: number) {
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
      adaptation_priority: "accessory",
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
        index === dayIndex ? { ...day, slots: [...day.slots, slot] } : day
      )),
    }));
    setExpandedDays((current) => new Set([...current, dayIndex]));
    setExpandedSlots((current) => new Set([...current, newSlotKey]));
  }

  async function save()"""

content = content.replace("  async function save()", draft_slot_fn)

# 2. Replace onClick={() => setPickerTarget({ dayIndex, slotIndex: null })}
content = content.replace(
    'onClick={() => setPickerTarget({ dayIndex, slotIndex: null })}',
    'onClick={() => addDraftSlot(dayIndex)}'
)

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx", "w") as f:
    f.write(content)
