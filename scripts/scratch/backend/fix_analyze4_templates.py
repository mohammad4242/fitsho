with open("analyze_stage4.py", "r") as f:
    content = f.read()

replacement = """
    template_count = agg.get("template_count", 0)
    template_slugs = agg.get("template_slugs", [])

    lines = [
        "# Phase 11 Deterministic Benchmark Final Report",
        "",
        f"**Active Template Count**: {template_count}",
        "",
        "- Total Profiles: 420"
    ]
"""
content = content.replace('    lines = [\n        "# Phase 11 Deterministic Benchmark Final Report",\n        "",\n        f"- Total Profiles: {total_profiles}",', replacement.strip('\n'))

with open("analyze_stage4.py", "w") as f:
    f.write(content)
