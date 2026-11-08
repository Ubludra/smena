"""Settings validation tests."""

from typing import Any

import pytest
from pydantic import ValidationError

from smena_api.config import Settings, get_settings


def _base_kwargs(**overrides: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "database_url": "postgresql+asyncpg://u:p@localhost:5432/db",
        "secret_key": "s" * 40,
    }
    kwargs.update(overrides)
    return kwargs


def test_cors_origins_parses_comma_separated_string() -> None:
    settings = Settings(**_base_kwargs(cors_origins="http://a, http://b"))  # type: ignore[arg-type]
    assert settings.cors_origins == ["http://a", "http://b"]


def test_log_level_normalized_and_validated() -> None:
    settings = Settings(**_base_kwargs(log_level="debug"))  # type: ignore[arg-type]
    assert settings.log_level == "DEBUG"
    with pytest.raises(ValidationError):
        Settings(**_base_kwargs(log_level="verbose"))  # type: ignore[arg-type]


def test_production_rejects_known_dev_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            **_base_kwargs(  # type: ignore[arg-type]
                environment="production",
                secret_key="dev-insecure-secret-key-change-me",
            )
        )


def test_production_rejects_short_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base_kwargs(environment="production", secret_key="short"))  # type: ignore[arg-type]


def test_production_rejects_dev_auth() -> None:
    """Fail-closed rule: production settings cannot enable the dev login."""
    with pytest.raises(ValidationError):
        Settings(  # type: ignore[call-arg]
            **_base_kwargs(
                environment="production",
                secret_key="s" * 40,
                enable_dev_auth=True,
            )
        )


def test_development_allows_dev_auth_but_requires_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(  # type: ignore[call-arg]
        **_base_kwargs(enable_dev_auth=True)
    )
    assert settings.enable_dev_auth is True
    # DATABASE_URL legitimately exists in CI/compose environments — remove it
    # to verify the constructor truly requires it.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(secret_key="x" * 40)  # database_url is required


def test_settings_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://env:env@h:5432/envdb")
    monkeypatch.setenv("SECRET_KEY", "env-secret-value")
    monkeypatch.setenv("LOG_LEVEL", "warning")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert (
            settings.database_url.get_secret_value() == "postgresql+asyncpg://env:env@h:5432/envdb"
        )
        assert settings.secret_key.get_secret_value() == "env-secret-value"
        assert settings.log_level == "WARNING"
    finally:
        get_settings.cache_clear()


def test_secrets_do_not_leak_into_repr_or_str() -> None:
    settings = Settings(**_base_kwargs(secret_key="super-secret-value"))  # type: ignore[arg-type]
    assert "super-secret-value" not in repr(settings)
    assert "super-secret-value" not in str(settings)
