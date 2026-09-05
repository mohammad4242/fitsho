import re

with open("../PROMPT5_PROGRESS.md", "r") as f:
    content = f.read()

new_limitations = """### Limitation Type
- **ROM**: 19/30 (63.3%)
- **axial_load**: 7/15 (46.7%)
- **balance**: 9/15 (60.0%)
- **impact**: 7/15 (46.7%)
- **none**: 134/240 (55.8%)
- **overhead**: 7/15 (46.7%)
- **training_cautions**: 23/45 (51.1%)"""

content = re.sub(r'### Limitation Type\n- \*\*ROM\*\*:.*?\n- \*\*none\*\*:.*?\n', new_limitations + "\n", content, flags=re.DOTALL)

with open("../PROMPT5_PROGRESS.md", "w") as f:
    f.write(content)
