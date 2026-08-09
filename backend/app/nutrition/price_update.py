# ruff: noqa: E501
"""Manual entry point: `python -m app.nutrition.price_update`."""

import asyncio
from argparse import ArgumentParser

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.nutrition.price_providers import configured_providers
from app.nutrition.price_scheduler import trigger_scheduled_update
from app.nutrition.price_update_service import run_price_update_async


async def main(*, catch_up: bool = False) -> None:
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=settings.food_price_provider_timeout_seconds, trust_env=False
    ) as client:
        if catch_up:
            await trigger_scheduled_update(settings, client)
            return
        with Session(get_engine(settings.database_url)) as db:
            await run_price_update_async(
                db,
                providers=configured_providers(settings, client),
                retry_attempts=settings.food_price_provider_retries,
            )


if __name__ == "__main__":
    parser = ArgumentParser(description="Refresh Fitsho food prices")
    parser.add_argument(
        "--catch-up",
        action="store_true",
        help="claim and run the latest due Saturday slot instead of a manual slot",
    )
    arguments = parser.parse_args()
    asyncio.run(main(catch_up=arguments.catch_up))
