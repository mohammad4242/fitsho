with open("analyze_stage4.py", "r") as f:
    content = f.read()

import re
content = re.sub(r'    lines = \[\n        "# Phase 11 Deterministic Benchmark Final Report",\n        "",\n        f"\*\*Active Template Count\*\*: \{template_count\}",\n        "",\n        "- Total Profiles: \{total_profiles\}"\n    \]\n        f"- PASS: \{passes\}",', 
r'''    lines = [
        "# Phase 11 Deterministic Benchmark Final Report",
        "",
        f"**Active Template Count**: {template_count}",
        "**Template Slugs**:",
        *(f"- {slug}" for slug in template_slugs),
        "",
        f"- Total Profiles: {total_profiles}",
        f"- PASS: {passes}",''', content)

with open("analyze_stage4.py", "w") as f:
    f.write(content)
