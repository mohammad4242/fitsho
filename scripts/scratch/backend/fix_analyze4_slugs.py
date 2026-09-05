with open("analyze_stage4.py", "r") as f:
    content = f.read()

replacement = """    template_count = agg.get("template_count", 0)
    template_slugs = agg.get("template_slugs", [])

    lines = [
        "# Phase 11 Deterministic Benchmark Final Report",
        "",
        f"**Active Template Count**: {template_count}",
        "**Template Slugs**:",
        *(f"- {slug}" for slug in template_slugs),
        "",
        f"- Total Profiles: {total_profiles}"
    ]"""
content = content.replace('    template_count = agg.get("template_count", 0)\n    template_slugs = agg.get("template_slugs", [])\n\n    lines = [\n        "# Phase 11 Deterministic Benchmark Final Report",\n        "",\n        f"**Active Template Count**: {template_count}",\n        "",\n        f"- Total Profiles: {total_profiles}"\n    ]', replacement)

with open("analyze_stage4.py", "w") as f:
    f.write(content)
