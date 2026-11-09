"""First-install administrator behavior, including rerun and privilege preservation."""

from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.security import verify_password
from app.db.session import async_session_factory
from app.models.auth_session import AuthSession
from app.models.staff import StaffUser
from app.models.user import User
from scripts.seed import read_admin_password, seed, validate_admin_password

PASSWORD = "FirstInstall@Test937"


@pytest.mark.parametrize("value", ["", "short", "Admin@123456", "password123456", "a" * 80])
def test_initializer_rejects_weak_or_oversized_passwords(value):
    with pytest.raises(ValueError):
        validate_admin_password(value)


def test_unattended_initializer_requires_explicit_secret(monkeypatch):
    monkeypatch.delenv("INITIAL_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(ValueError, match="INITIAL_ADMIN_PASSWORD"):
        read_admin_password()


async def test_first_install_uses_staff_account_and_preserves_existing_password(client):
    username = "seed_" + uuid4().hex[:12]
    try:
        await seed(username, password_provider=lambda: PASSWORD)
        async with async_session_factory() as session:
            row = await session.scalar(select(StaffUser).where(StaffUser.username == username))
            assert row and row.is_superuser and row.is_active
            original_hash = row.hashed_password
            assert verify_password(PASSWORD, original_hash)
            assert await session.scalar(select(User.id).where(User.username == username)) is None
        response = await client.post(
            "/api/v1/admin/auth/login", json={"username": username, "password": PASSWORD}
        )
        assert response.status_code == 200, response.text

        def no_prompt():
            raise AssertionError("Existing administrator must not ask for or replace a password")

        await seed(username, password_provider=no_prompt)
        async with async_session_factory() as session:
            row = await session.scalar(select(StaffUser).where(StaffUser.username == username))
            assert row.hashed_password == original_hash
            row.is_superuser = False
            await session.commit()
        with pytest.raises(ValueError, match="同名账号"):
            await seed(username, password_provider=lambda: PASSWORD)
        async with async_session_factory() as session:
            row = await session.scalar(select(StaffUser).where(StaffUser.username == username))
            assert not row.is_superuser
    finally:
        async with async_session_factory() as session:
            row_id = await session.scalar(
                select(StaffUser.id).where(StaffUser.username == username)
            )
            if row_id:
                await session.execute(
                    delete(AuthSession).where(
                        AuthSession.scope == "staff", AuthSession.subject_id == row_id
                    )
                )
                await session.execute(delete(StaffUser).where(StaffUser.id == row_id))
                await session.commit()
