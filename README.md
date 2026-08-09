# Fitsho

Fitsho is a FastAPI/PostgreSQL backend with a React/Vite frontend for deterministic training and
nutrition planning. Nutrition calculations, safety decisions, food quantities, prices, and
physician-review state are owned by Fitsho; external AI is optional and limited to explicitly
consented food-photo estimation.

## Local development

```bash
cp .env.example backend/.env
docker compose up --build
```

The compose stack starts PostgreSQL, runs Alembic to head, and starts the backend. Run the frontend
separately:

```bash
cd frontend
npm install
npm run dev
```

The frontend is available at `http://localhost:5173`; Vite proxies `/api` and `/media` to the
backend. Do not commit `backend/.env`, provider keys, encryption keys, or private-file signing keys.

## Nutrition Core

The Nutrition Core provides versioned scientific estimates, a verified food-composition catalogue,
weekly budget-aware plans, immutable price and plan history, consumption tracking, mandatory
physician review, secure laboratory records, and physician-managed supplements.

Useful commands:

```bash
cd backend
uv run python -m app.nutrition.price_update
uv run python -m app.nutrition.retention_cleanup
uv run pytest tests/nutrition
```

Automatic food-price refresh checks ten isolated public sources every Saturday at 12:00
`Asia/Tehran`, with restart catch-up and a PostgreSQL advisory lock. It requires three distinct
sources, removes outliers, and stores the mean plus immutable history. No API key is enabled or
required by default. The planner always reads accepted prices from Fitsho's database and never
contacts a marketplace during a user request. Private-file retention cleanup runs daily.

Nutrition documentation:

- [Architecture](docs/nutrition-implementation-design.md)
- [Scientific and micronutrient policy](docs/nutrition-scientific-policy.md)
- [Planner scoring and repair](docs/nutrition-weekly-planner.md)
- [Food provenance](docs/nutrition-food-data-provenance.md)
- [Price providers and freshness](docs/nutrition-pricing.md)
- [Medical review and supplements](docs/nutrition-medical-review.md)
- [Security and privacy](docs/nutrition-security-privacy.md)
- [API](docs/nutrition-api.md)
- [Migration notes](docs/nutrition-migrations.md)

## AI model administration

The OpenCode Zen key remains only in `backend/.env`:

```env
OPENCODE_ZEN_API_KEY="your-key"
```

An administrator can open `/admin/ai-models` and manage workout-generation
models without restarting the backend:

1. Select **Sync Zen** to fetch the current Zen model catalogue.
2. Classify every newly discovered disabled model with its API kind and billing class.
3. Test the model, then enable it when the test succeeds.
4. Choose **Manual** and select one enabled model, or choose **Automatic** and order
   enabled free models for fallback.

The next workout-generation request reads the saved routing setting directly from
the database. Automatic routing tries enabled free models in the configured order.

OpenRouter credentials are stored through the same administrator workflow, encrypted at rest with
`AI_CREDENTIAL_ENCRYPTION_KEY`, and masked in API responses. Empty OpenRouter configuration keeps
food-photo estimation disabled without affecting deterministic Nutrition behavior.
