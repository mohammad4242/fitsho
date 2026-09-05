import re

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.test.tsx", "r") as f:
    content = f.read()

content = content.replace(
    'await user.click(screen.getByRole("button", { name: "افزودن حرکت" }));',
    'await user.click(screen.getByRole("button", { name: "افزودن حرکت" }));\n  await user.click((await screen.findAllByRole("button", { name: "انتخاب از کتابخانه" }))[0]);'
)

# For search Input, my search input placeholder might be "جست‌وجو با نام انگلیسی یا فارسی..." instead of "جست‌وجو با نام فارسی یا انگلیسی…" depending on the codebase, but let's leave it as is if it's there.
with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.test.tsx", "w") as f:
    f.write(content)
