import re
import os

for root, _, files in os.walk("backend/tests"):
    for file in files:
        if not file.endswith(".py"):
            continue
        filepath = os.path.join(root, file)
        with open(filepath, "r") as f:
            content = f.read()
        
        # Replace superset_group=..., \n sets=... with superset_group=..., \n superset_exercise_id=None, \n superset_exercise_slug_hint=None, \n sets=...
        # Let's write a regex that matches superset_group line, up to sets= line.
        
        new_content = re.sub(
            r'(superset_group=[^,]+,[\s\n]*)(sets=)',
            r'\1superset_exercise_id=None,\n        superset_exercise_slug_hint=None,\n        \2',
            content
        )
        if new_content != content:
            with open(filepath, "w") as f:
                f.write(new_content)
