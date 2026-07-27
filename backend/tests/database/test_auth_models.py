from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User


def test_user_defaults_to_non_admin(db: Session) -> None:
    user = User(email="member@example.com", password_hash="hash")
    db.add(user)
    db.flush()

    assert user.is_admin is False


def test_database_defaults_user_to_non_admin(db: Session) -> None:
    is_admin = db.execute(
        text(
            """
            INSERT INTO users (id, email, password_hash)
            VALUES (:id, :email, :password_hash)
            RETURNING is_admin
            """
        ),
        {
            "id": uuid4(),
            "email": "database-default@example.com",
            "password_hash": "hash",
        },
    ).scalar_one()

    assert is_admin is False


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
