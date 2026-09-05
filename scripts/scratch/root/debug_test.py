import re

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.test.tsx", "r") as f:
    content = f.read()

content = content.replace(
    'await user.click((await screen.findAllByRole("button", { name: "انتخاب از کتابخانه" }))[0]);',
    'screen.debug();\n  await user.click((await screen.findAllByRole("button", { name: "انتخاب از کتابخانه" }))[0]);'
)

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.test.tsx", "w") as f:
    f.write(content)
