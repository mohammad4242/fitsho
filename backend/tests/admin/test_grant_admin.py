import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.exceptions import AdminUserNotFoundError
from app.admin.service import grant_admin
from app.auth.models import User


def test_grant_admin_normalizes_email_and_is_idempotent(db: Session) -> None:
    user = User(email="admin@example.com", password_hash="hash")
    db.add(user)
    db.commit()

    first = grant_admin(db, " ADMIN@example.com ")
    second = grant_admin(db, "admin@example.com")

    assert first.id == user.id
    assert second.id == user.id
    assert second.is_admin is True


def test_grant_admin_rejects_unknown_email_without_creating_user(db: Session) -> None:
    with pytest.raises(AdminUserNotFoundError):
        grant_admin(db, "missing@example.com")

    assert db.scalar(select(User).where(User.email == "missing@example.com")) is None


def test_grant_admin_command_promotes_existing_user(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import app.admin.grant_admin as command

    user = User(email="command-admin@example.com", password_hash="hash")
    db.add(user)
    db.commit()
    monkeypatch.setattr(command, "get_engine", lambda _: db.get_bind())

    exit_code = command.main(["command-admin@example.com"])
    db.expire_all()
    promoted_user = db.get(User, user.id)

    assert exit_code == 0
    assert promoted_user is not None
    assert promoted_user.is_admin is True
    assert capsys.readouterr().out == (
        "Administrator access granted to command-admin@example.com.\n"
    )
