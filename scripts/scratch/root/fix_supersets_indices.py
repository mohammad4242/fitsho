import re

with open("backend/app/workouts/program_engine/supersets.py", "r") as f:
    content = f.read()

content = content.replace(
    'if not is_valid:\n            print(f"REJECTED: len={len(indices)}, adj={indices[1] == indices[0] + 1 if len(indices) == 2 else False}, safe={safe_superset_category(members[0], members[1]) if len(indices) == 2 else None}")',
    'if not is_valid:\n            print(f"REJECTED: indices={indices}, safe={safe_superset_category(members[0], members[1]) if len(indices) == 2 else None}")'
)

with open("backend/app/workouts/program_engine/supersets.py", "w") as f:
    f.write(content)
