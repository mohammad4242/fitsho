# Nutrition migration notes

Nutrition Core is additive from the existing training schema and preserves training users. Product
mode defaults and existing workout records are not rewritten. Shared profile identity remains one
record per user.

Key migration milestones:

- `20260805_33` to `20260805_36`: Nutrition profile, scientific targets, and medical policy.
- `20260808_37` to `20260808_41`: pricing, micronutrient policy, canonical foods, and immutable quotes.
- `20260809_42` to `20260809_43`: weekly planner and approved Iranian ingredient catalogue.
- `20260809_44` to `20260809_49`: plan editing, tracking, photo estimates, review, labs, and supplements.
- `20260809_50`: security audit, operational metrics, upload limits, and private-file lifecycle.
- `20260809_51`: idempotent repair for legacy databases stamped during a partial Task 12 rollout.

Legacy cooked/grilled food identities are retired rather than deleted. Historical plan, quote,
review, lab, supplement, and tracking snapshots remain immutable or audit-preserving. Composition and
price tables remain separate.

Upgrade the current database:

```bash
cd backend
uv run alembic upgrade head
uv run alembic heads
```

Production deployment should back up PostgreSQL, run the migration as a single release step, verify
one head, and then start application workers. Migration `20260809_51` is safe on both complete and
historically drifted Task 12 schemas because it inspects existing columns and indexes before repair.
