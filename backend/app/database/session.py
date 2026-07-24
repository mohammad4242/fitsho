from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.config import Settings, get_settings


@lru_cache
def get_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def get_db(settings: Settings = Depends(get_settings)) -> Iterator[Session]:  # noqa: B008
    with Session(get_engine(settings.database_url)) as session:
        yield session
