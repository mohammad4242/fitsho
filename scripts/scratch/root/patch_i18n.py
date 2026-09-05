import json
import re

for file_path in ["frontend/src/i18n/fa.ts", "frontend/src/i18n/en.ts"]:
    with open(file_path, "r") as f:
        content = f.read()
    
    if "fa.ts" in file_path:
        methods = """      methods: {
        standard: "استاندارد",
        superset: "سوپرست",
        drop_set: "دراپ‌ست",
      },"""
        editor = """    templateEditor: {
      executionMethod: "روش اجرا",
      movement: "حرکت",
      movement1: "حرکت اول",
      movement2: "حرکت دوم",
      emptyMovement: "انتخاب نشده",
      addExercise: "افزودن حرکت",
      chooseFromLibrary: "انتخاب از کتابخانه حرکات",
      removeExercise: "حذف",
      removeExerciseAria: "حذف حرکت {{name}}",
      exerciseDetails: "جزئیات",
      slotCountError: "تعداد حرکات هر روز باید بین ۵ تا ۹ باشد.",
      slotCountHint: "حداقل ۵ حرکت","""
    else:
        methods = """      methods: {
        standard: "Standard",
        superset: "Superset",
        drop_set: "Drop Set",
      },"""
        editor = """    templateEditor: {
      executionMethod: "Execution Method",
      movement: "Movement",
      movement1: "Movement 1",
      movement2: "Movement 2",
      emptyMovement: "Not selected",
      addExercise: "Add Exercise",
      chooseFromLibrary: "Choose from library",
      removeExercise: "Remove",
      removeExerciseAria: "Remove {{name}}",
      exerciseDetails: "Details",
      slotCountError: "Each day must have 5 to 9 exercises.",
      slotCountHint: "Minimum 5 exercises","""
      
    # I will replace `methods: { ... }` 
    content = re.sub(r'methods: \{[^\}]+\},', methods, content)
    
    # I will add new entries to `templateEditor: {`
    # First remove the old ones that might conflict, or just replace the beginning of templateEditor
    content = re.sub(r'    templateEditor: \{', editor, content)
    
    with open(file_path, "w") as f:
        f.write(content)

