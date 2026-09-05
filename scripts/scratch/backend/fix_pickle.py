import re

with open("tests/workouts/program_engine/phase11_benchmark.py", "r") as f:
    content = f.read()

# I will just write a very clean file replacing the entire end of the file
replacement = """
_GLOBAL_CATALOG_BY_SEX = {}
_GLOBAL_REFERENCES = None
_GLOBAL_DETERMINISM_REPEATS = 1

def _run_single(args):
    i, profile = args
    from app.workouts.program_engine.engine import generate_program
    from tests.workouts.program_engine.phase11_benchmark import profile_to_request, apply_catalog_constraints, RULESET, canonical_fingerprint, _case_record, _GLOBAL_CATALOG_BY_SEX, _GLOBAL_REFERENCES, _GLOBAL_DETERMINISM_REPEATS
    req = profile_to_request(profile)
    c_catalog = _GLOBAL_CATALOG_BY_SEX[profile.sex]
    req = apply_catalog_constraints(req, profile, c_catalog)
    res = generate_program(req, c_catalog, RULESET, reference_templates=_GLOBAL_REFERENCES)
    rep = [
        generate_program(req, c_catalog, RULESET, reference_templates=_GLOBAL_REFERENCES)
        for _ in range(max(1, _GLOBAL_DETERMINISM_REPEATS))
    ]
    fgps = tuple(canonical_fingerprint(item) for item in [res] + rep)
    record = _case_record(profile, req, res, c_catalog, fgps)
    if (i + 1) % 20 == 0:
        print(f"Processed {i + 1}", flush=True)
    return record

def run_benchmark(
    db: Session,
    output_dir: Path,
    *,
    determinism_repeats: int = 3,
) -> dict[str, object]:
    from concurrent.futures import ProcessPoolExecutor
    service = _service_for_benchmark(db)
    references = load_template_references(db)
    catalog_by_sex = {sex: service._load_catalog(sex) for sex in (None, Sex.MALE, Sex.FEMALE)}
    catalog = catalog_by_sex[None]
    if len(catalog) < 100 or len(references) < 15:
        raise RuntimeError(
            "real catalog snapshot is too small: "
            f"exercises={len(catalog)} templates={len(references)}"
        )
    catalog_hash = service._catalog_hash(catalog)
    reference_hash = service._template_reference_hash(references)

    profiles = benchmark_profiles()
    print(f"Running benchmark for {len(profiles)} profiles with ProcessPoolExecutor...", flush=True)
    
    global _GLOBAL_CATALOG_BY_SEX, _GLOBAL_REFERENCES, _GLOBAL_DETERMINISM_REPEATS
    _GLOBAL_CATALOG_BY_SEX = catalog_by_sex
    _GLOBAL_REFERENCES = references
    _GLOBAL_DETERMINISM_REPEATS = determinism_repeats

    with ProcessPoolExecutor(max_workers=2) as executor:
        records = list(executor.map(_run_single, enumerate(profiles)))

    negative_cases: list[dict[str, object]] = []
    for profile in NEGATIVE_PROFILES:
        request = profile_to_request(profile, enforce_matrix=False)
        case_catalog = catalog_by_sex[profile.sex]
        result = generate_program(request, case_catalog, RULESET, reference_templates=references)
        negative_cases.append(
            {
                "input": _jsonable(asdict(profile)),
                "request_days": request.available_training_days,
                "error_code": result.error_code.value if result.error_code else None,
                "errors": result.errors,
                "rejected_correctly": result.error_code is not None
                and result.error_code.value == "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
            }
        )

    payload: dict[str, object] = {
        "phase": 11,
        "ruleset": RULESET.version,
        "engine_version": RULESET.engine_version,
        "catalog": {
            "exercise_count": len(catalog),
            "template_count": len(references),
            "catalog_hash": catalog_hash,
            "template_hash": reference_hash,
        },
        "supported_matrix": SUPPORTED_MATRIX,
        "aggregate": _aggregate(records, len(NEGATIVE_PROFILES)),
        "determinism": {
            "repeats": determinism_repeats,
        },
        "profiles": records,
        "negative_profiles": negative_cases,
    }

    # Add template info to aggregate
    payload["aggregate"]["template_count"] = len(references)
    payload["aggregate"]["template_slugs"] = [ref.slug for ref in references]

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "phase11-benchmark.json"
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    
    print(f"Benchmark results saved to {output_path}", flush=True)

    return payload
"""

before = content.split("def run_benchmark(")[0]
new_content = before + replacement

# Wait, there's `def main` at the end!
main_func = """
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 11 deterministic benchmark")
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "BENCHMARK_DATABASE_URL",
            "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho",
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("var/benchmarks/phase11"))
    parser.add_argument("--determinism-repeats", type=int, default=3)
    args = parser.parse_args(argv)
    engine = create_engine(args.database_url)
    try:
        with Session(engine) as db:
            payload = run_benchmark(
                db,
                args.output_dir,
                determinism_repeats=max(1, args.determinism_repeats),
            )
        aggregate = cast(Mapping[str, object], payload["aggregate"])
        passes = cast(Mapping[str, int], aggregate["category_counts"]).get("PASS", 0)
        total = cast(int, aggregate["profiles_tested"])
        print(f"\\nBenchmark Complete: {passes}/{total} profiles passed.")
        return 0
    except Exception as e:
        print(f"Benchmark failed: {e}")
        return 1
"""
new_content += main_func

with open("tests/workouts/program_engine/phase11_benchmark.py", "w") as f:
    f.write(new_content)
