with open("analyze_stage4.py", "r") as f:
    content = f.read()

replacement = """    if template_count != 49:
        ready = False
        blocking_reasons.append(f"Template count is {template_count}, expected 49")

    lines.append("## Final Verdict")"""
content = content.replace('    lines.append("## Final Verdict")', replacement)

with open("analyze_stage4.py", "w") as f:
    f.write(content)
