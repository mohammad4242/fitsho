from pathlib import Path
p = Path("tests/workouts/program_engine/test_golden_scenarios.py")
content = p.read_text()
content = content.replace(
    'training_experience="intermediate",\n        training_age_months=24,',
    'training_experience="advanced",\n        training_age_months=60,'
)
p.write_text(content)
