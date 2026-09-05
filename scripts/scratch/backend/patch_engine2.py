import sys
with open('app/workouts/program_engine/engine.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'return ProgramGenerationResult(' in line and 'errors=errors' in lines[i+3]:
        lines.insert(i, "    print('RETURNING RESULT WITH ERRORS:', errors)\n")
        break

with open('app/workouts/program_engine/engine.py', 'w') as f:
    f.writelines(lines)
