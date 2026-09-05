import re

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx", "r") as f:
    content = f.read()

content = re.sub(r'\s*<label className="admin-field">\s*<span>\{t\("admin.templateEditor.goal"\)\}</span>\s*<select value=\{form.fitness_goal\} onChange=\{\(event\) => updateField\("fitness_goal", event.target.value as AdminTrainingProgramTemplateWrite\["fitness_goal"\]\)\}>\s*\{fitnessGoals\.map\(\(goal\) => <option key=\{goal\} value=\{goal\}>\{t\(`onboarding\.fitnessGoal\.\$\{goal\}`\)\}</option>\)\}\s*</select>\s*</label>', '', content)

content = re.sub(r'\s*fitness_goal:\s*"build_muscle",\n', '\n', content)
content = re.sub(r'\s*fitness_goal:\s*form\.fitness_goal,\n', '\n', content)

with open("frontend/src/features/admin/AdminTrainingTemplateEditorPage.tsx", "w") as f:
    f.write(content)
