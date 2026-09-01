# ruff: noqa: E501
"""Manual entry point: `python -m app.nutrition.price_update`."""

import asyncio
from argparse import ArgumentParser

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.nutrition.price_execution import resolve_price_update_execution
from app.nutrition.price_providers import configured_providers
from app.nutrition.price_scheduler import trigger_scheduled_update
from app.nutrition.price_update_service import run_price_update_async


async def main(*, catch_up: bool = False) -> None:
    settings = get_settings()
    async with (
        httpx.AsyncClient(
            timeout=settings.food_price_provider_timeout_seconds, trust_env=False
        ) as client,
        httpx.AsyncClient(
            timeout=settings.agent_service_connect_timeout_seconds, trust_env=False
        ) as agent_client,
    ):
        if catch_up:
            await trigger_scheduled_update(settings, client, agent_http_client=agent_client)
            return
        with Session(get_engine(settings.database_url)) as db:
            execution = resolve_price_update_execution(
                db,
                settings=settings,
                price_http_client=client,
                agent_http_client=agent_client,
                direct_provider_factory=lambda: configured_providers(settings, client),
            )
            await run_price_update_async(
                db,
                providers=execution.providers,
                agent_researcher=execution.agent_researcher,
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
