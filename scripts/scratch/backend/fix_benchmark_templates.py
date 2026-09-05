with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

# Add to run_benchmark output:
replacement = """    return {
        "aggregate": {
            "template_count": len(references),
            "template_slugs": [ref.slug for ref in references],
            **aggregate
        },
        "records": records,
        "negative_records": negative,
    }"""
content = content.replace('    return {"aggregate": aggregate, "records": records, "negative_records": negative}', replacement)

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(content)
