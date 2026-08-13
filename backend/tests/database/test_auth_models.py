from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User


def test_auth_schema_supports_phone_accounts_and_one_time_credentials(db: Session) -> None:
    inspector = inspect(db.get_bind())
    user_columns = {column["name"]: column for column in inspector.get_columns("users")}

    assert user_columns["email"]["nullable"] is True
    assert user_columns["password_hash"]["nullable"] is True
    assert user_columns["phone_number"]["nullable"] is True
    assert {"password_reset_tokens", "phone_otp_challenges"}.issubset(inspector.get_table_names())
    otp_indexes = {index["name"]: index for index in inspector.get_indexes("phone_otp_challenges")}
    assert otp_indexes["uq_phone_otp_challenges_active_phone"]["unique"] is True


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


def test_phone_only_user_is_supported(db: Session) -> None:
    user = User(phone_number="+989123456789")
    db.add(user)
    db.flush()

    assert user.email is None
    assert user.password_hash is None


def test_user_requires_at_least_one_login_identifier(db: Session) -> None:
    db.add(User())

    with pytest.raises(IntegrityError):
        db.flush()


def test_user_phone_number_is_unique(db: Session) -> None:
    db.add(User(phone_number="+989123456789"))
    db.flush()
    db.add(User(phone_number="+989123456789"))

    with pytest.raises(IntegrityError):
        db.flush()


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
