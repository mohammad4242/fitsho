with open("analyze_stage4.py", "r") as f:
    content = f.read()

content = content.replace(
    'if fallback.get("rejection_categories", {}).get("VALIDATION_FAILURE", 0) > 0:\n        # Wait, the prompt says "every UNSAT is individually justified as legitimate" and "engine bug = 0".\n        pass',
    'if fallback.get("rejection_categories", {}).get("VALIDATION_FAILURE", 0) > 0:\n        ready = False\n        blocking_reasons.append("VALIDATION_FAILURE in template rejections (> 0)")'
)

with open("analyze_stage4.py", "w") as f:
    f.write(content)
