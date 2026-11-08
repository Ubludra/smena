"""Application settings (12-factor: everything from environment variables).

Secrets are held in ``SecretStr`` so they cannot leak via ``repr()`` or logs.
``database_url`` and ``secret_key`` are REQUIRED — the app refuses to start
without them instead of silently falling back to an insecure default.

Authentication policy (fail-closed):

* ``enable_dev_auth`` gates the dev-only login endpoint. It MUST be false in
  production; the model validator below refuses to construct production
  settings with the dev login enabled, so a misconfigured deploy cannot
  silently expose it.
* MAX launch-context verification is not implemented yet (see
  ``integrations/max_auth.py``); the API exposes it as an explicit 501.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["development", "staging", "production", "test"]

# Reject the well-known dev placeholder if someone tries to use it in prod.
_KNOWN_INSECURE_KEYS = frozenset({"dev-insecure-secret-key-change-me"})
_MIN_PRODUCTION_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Runtime configuration, populated from environment / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Environment = "development"
    log_level: str = "INFO"

    database_url: SecretStr
    test_database_url: SecretStr | None = None

    secret_key: SecretStr

    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    # NoDecode: accept a plain comma-separated string from the environment
    # (parsed by _split_cors_origins) instead of pydantic-settings' default
    # JSON decoding for complex types.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )

    # --- Authentication ---
    # Dev-only login (POST /api/v1/auth/dev-login). Never allowed in production;
    # see _check_invariants for the fail-closed validator.
    enable_dev_auth: bool = True
    # Lifetime of issued access tokens.
    access_token_ttl_seconds: int = Field(default=12 * 3600, gt=0)

    # Reserved for MAX launch-context verification (HMAC key; official
    # algorithm implemented in integrations/max_auth.py). Without it the
    # MAX login endpoint honestly reports MAX_NOT_CONFIGURED.
    max_bot_token: SecretStr | None = None
    # WebAuthn RP and exact HTTPS origin; absent values disable passkey flows.
    passkey_rp_id: str | None = None
    passkey_origin: str | None = None
    # Official recommendation: treat init data older than 1 hour as stale.
    max_init_data_max_age_seconds: int = Field(default=3600, gt=0)

    # --- Uploaded files ---
    # Directory for teacher uploads. Created lazily on first upload; must be a
    # dedicated mount in docker (compose provides the `uploads_data` volume).
    upload_dir: str = "/data/uploads"
    # Hard size ceiling for one upload (20 MiB) — streamed, never fully
    # buffered in memory beyond one chunk.
    upload_max_bytes: int = Field(default=20 * 1024 * 1024, gt=0)

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if level not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return level

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        # Accept a comma-separated string from the environment.
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _check_invariants(self) -> "Settings":
        if self.environment == "production":
            secret = self.secret_key.get_secret_value()
            if secret in _KNOWN_INSECURE_KEYS:
                raise ValueError("SECRET_KEY must be changed in production")
            if len(secret) < _MIN_PRODUCTION_SECRET_LENGTH:
                raise ValueError(
                    f"SECRET_KEY must be at least {_MIN_PRODUCTION_SECRET_LENGTH} "
                    "characters in production"
                )
            if self.enable_dev_auth:
                raise ValueError("ENABLE_DEV_AUTH must be false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
