import re

with open("analyze_stage4.py", "r") as f:
    content = f.read()

# Fix 1
content = content.replace(
    'f"Category sum ({passes + pass_c + quality_issue + unsat + bugs}) does not equal total profiles ({total_profiles})"',
    'f"Category sum ({passes + pass_c + quality_issue + unsat + bugs}) != total profiles ({total_profiles})"'
)

# Fix 2
content = re.sub(r'# "no unexplained semantic substitution failure" implies bugs > 0 or safety_v > 0 will catch it, or maybe sub_no_valid > 0 \?', '# "no unexplained semantic substitution failure" implies bugs > 0 or safety_v > 0 will catch it.', content)

# Fix 3
content = content.replace(
    '# Actually, the benchmark might only test determinism for some, but wait, the prompt says "Add assertions/tests for: ... determinism denominator == total profiles". So I should assert it or use total_profiles.',
    '# Assert determinism.'
)

# Fix 4
content = content.replace(
    'f"- Category sum equals total profiles: {passes + pass_c + quality_issue + unsat + bugs == total_profiles}"',
    'f"- Category sum equals total: {passes + pass_c + quality_issue + unsat + bugs == total_profiles}"'
)

with open("analyze_stage4.py", "w") as f:
    f.write(content)
