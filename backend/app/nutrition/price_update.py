# ruff: noqa: E501
"""Manual entry point: `python -m app.nutrition.price_update`."""

import asyncio

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.nutrition.price_providers import configured_providers
from app.nutrition.price_update_service import run_price_update


async def main() -> None:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.food_price_provider_timeout_seconds, trust_env=False) as client:
        with Session(get_engine(settings.database_url)) as db:
            run_price_update(db, providers=configured_providers(settings, client))


if __name__ == "__main__":
    asyncio.run(main())
