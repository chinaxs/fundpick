"""Production settings must not inherit development credentials or origins."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

SAFE_PRODUCTION = {
    "APP_ENV": "production",
    "DEBUG": False,
    "SECRET_KEY": "safe-production-signing-key-" + "x" * 32,
    "MYSQL_HOST": "db.internal",
    "MYSQL_USER": "fundpick_api",
    "MYSQL_PASSWORD": "unique-database-password",
    "MYSQL_DB": "fundpick_prod",
    "CORS_ORIGINS": "https://fundpick.example.com",
}


def test_production_accepts_explicit_secure_settings():
    settings = Settings(_env_file=None, **SAFE_PRODUCTION)
    assert settings.is_production
    assert settings.cors_origin_list == ["https://fundpick.example.com"]


@pytest.mark.parametrize(
    "override",
    [
        {"SECRET_KEY": "change-me"},
        {"MYSQL_USER": "root"},
        {"MYSQL_PASSWORD": ""},
        {"MYSQL_DB": "test_study"},
        {"CORS_ORIGINS": "http://fundpick.example.com"},
        {"CORS_ORIGINS": "https://*.example.com"},
        {"CORS_ORIGIN_REGEX": ".*"},
        {"DEBUG": True},
        {"AI_ENABLED": True},
    ],
)
def test_production_rejects_unsafe_settings(override):
    with pytest.raises(ValidationError, match="Invalid production configuration"):
        Settings(_env_file=None, **(SAFE_PRODUCTION | override))


def test_test_environment_rejects_shared_non_test_database():
    with pytest.raises(ValidationError, match="dedicated MySQL database"):
        Settings(_env_file=None, APP_ENV="test", MYSQL_DB="fundpick")
