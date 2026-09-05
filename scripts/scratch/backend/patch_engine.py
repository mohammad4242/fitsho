import sys
with open('app/workouts/program_engine/engine.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'errors = (' in line and '"PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED",' in lines[i+1]:
        lines.insert(i, "    print('BEFORE TUPLE: ', collected_errors)\n")
        lines.insert(i+7, "    print('AFTER TUPLE: ', errors)\n")
        break

with open('app/workouts/program_engine/engine.py', 'w') as f:
    f.writelines(lines)
