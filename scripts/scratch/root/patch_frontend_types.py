import re

with open("frontend/src/features/admin/types.ts", "r") as f:
    content = f.read()

read_old = """  rest_seconds: number;
  exercise: AdminTrainingTemplateExercise | null;
};"""

read_new = """  rest_seconds: number;
  exercise: AdminTrainingTemplateExercise | null;
  superset_exercise: AdminTrainingTemplateExercise | null;
};"""

content = content.replace(read_old, read_new)

write_old = """  adaptation_priority: TrainingTemplateSlotPriority;
  superset_group: string | null;
  sets: number;"""

write_new = """  adaptation_priority: TrainingTemplateSlotPriority;
  superset_group: string | null;
  superset_exercise_id: string | null;
  sets: number;"""

content = content.replace(write_old, write_new)

with open("frontend/src/features/admin/types.ts", "w") as f:
    f.write(content)
