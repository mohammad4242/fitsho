from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User


def test_user_email_is_unique(db: Session) -> None:
    db.add(User(email="same@example.com", password_hash="hash-1"))
    db.flush()
    db.add(User(email="same@example.com", password_hash="hash-2"))

    with pytest.raises(IntegrityError):
        db.flush()


def test_deleting_user_deletes_sessions(db: Session) -> None:
    user = User(email="delete@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    session = AuthSession(
        user_id=user.id,
        token_hash="a" * 64,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(session)
    db.flush()

    db.delete(user)
    db.flush()

    assert db.scalar(select(AuthSession).where(AuthSession.id == session.id)) is None
