import re

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx", "r") as f:
    content = f.read()

content = content.replace("function addDraftSlot(dayIndex: number) {", "const addDraftSlot = (dayIndex: number) => {")

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx", "w") as f:
    f.write(content)
