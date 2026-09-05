import sys
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS, RETIRED_REDUNDANT_TEMPLATE_SLUGS, RETIRED_UNSUPPORTED_TEMPLATE_SLUGS, STRUCTURAL_RECLASSIFIED_TEMPLATE_SLUGS
print(f"Number of templates: {len(TRAINING_PROGRAM_TEMPLATE_SEEDS)}")
cells = set()
for t in TRAINING_PROGRAM_TEMPLATE_SEEDS:
    cells.add((t.training_level, t.days_per_week))
print("Supported Experience x Days:")
for cell in sorted(cells):
    print(f"  {cell[0]} x {cell[1]} days")
