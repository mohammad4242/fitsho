from audit_phase11_benchmark import benchmark_profiles
for p in benchmark_profiles():
    if p.profile_id == '641215b2-32b0-56da-8276-8fde09dbff09':
        print(f"FOUND IT: {p.experience_level.value}, {p.resistance_days}, {p.variant}")
        import sys; sys.exit(0)
print("NOT FOUND IN AUDIT BENCHMARK PROFILES")
