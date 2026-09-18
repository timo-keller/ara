"""Runtime configuration loaded from the environment."""

import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

SECRETS_DIRECTORY = Path("/run/secrets")
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:////app/data/ara.db"


class ConfigurationError(ValueError):
    """Raised when an environment setting cannot be safely loaded."""


_SECRET_FILE_SETTINGS = {
    "ARA_OIDC_CLIENT_SECRET_FILE": "oidc_client_secret",
    "ARA_SESSION_SECRET_FILE": "session_secret",
    "ARA_OWNER_SUBJECTS_FILE": "owner_subjects",
}
_DIRECT_SECRET_SETTINGS = {
    "ARA_OIDC_CLIENT_SECRET": "oidc_client_secret",
    "ARA_SESSION_SECRET": "session_secret",
    "ARA_OWNER_SUBJECTS": "owner_subjects",
}
_ENVIRONMENT_SETTINGS = {
    "ARA_DATABASE_URL": "database_url",
    "ARA_PUBLIC_URL": "public_url",
    "ARA_OIDC_ISSUER_URL": "oidc_issuer_url",
    "ARA_OIDC_CLIENT_ID": "oidc_client_id",
    "ARA_OIDC_SCOPES": "oidc_scopes",
    "ARA_AUDIT_RETENTION_DAYS": "audit_retention_days",
}


def _read_secret_file(setting_name: str, filename: str, secrets_directory: Path) -> str:
    """Read one Docker secret, refusing paths outside the secret mount."""
    secret_directory = secrets_directory.resolve()
    path = Path(filename)
    if not path.is_absolute():
        path = secret_directory / path

    try:
        path = path.resolve(strict=True)
    except OSError as error:
        message = f"{setting_name} points to an unreadable secret file {filename!r}"
        raise ConfigurationError(message) from error

    if not path.is_relative_to(secret_directory):
        message = f"{setting_name} must point to a file under {secrets_directory}"
        raise ConfigurationError(message)

    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as error:
        message = f"{setting_name} points to an unreadable secret file {filename!r}"
        raise ConfigurationError(message) from error

    if not value:
        message = f"{setting_name} points to an empty secret file {filename!r}"
        raise ConfigurationError(message)
    return value


def load_environment(
    environment: Mapping[str, str],
    secrets_directory: Path = SECRETS_DIRECTORY,
) -> dict[str, Any]:
    """Load supported settings and resolve the explicitly supported ``_FILE`` values."""
    values: dict[str, Any] = {
        field_name: environment[environment_name]
        for environment_name, field_name in _ENVIRONMENT_SETTINGS.items()
        if environment_name in environment
    }

    for file_setting, field_name in _SECRET_FILE_SETTINGS.items():
        direct_setting = next(
            name
            for name, direct_field in _DIRECT_SECRET_SETTINGS.items()
            if direct_field == field_name
        )
        has_direct_value = direct_setting in environment
        has_file_value = file_setting in environment
        if has_direct_value and has_file_value:
            message = f"{direct_setting} and {file_setting} cannot both be set"
            raise ConfigurationError(message)
        if has_file_value:
            values[field_name] = _read_secret_file(
                file_setting, environment[file_setting], secrets_directory
            )
        elif has_direct_value:
            values[field_name] = environment[direct_setting]

    return values


class _EnvironmentSource(PydanticBaseSettingsSource):
    """Pydantic settings source with Docker-secret file support."""

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        """Implement the source protocol; values are collected in ``__call__``."""
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        return load_environment(os.environ)


class Settings(BaseSettings):
    """Typed ARA runtime settings.

    Secrets intentionally use :class:`~pydantic.SecretStr`, so their values are
    redacted in settings representations and validation errors.
    """

    model_config = SettingsConfigDict(env_prefix="ARA_", extra="ignore")

    database_url: str = Field(default=DEFAULT_DATABASE_URL, min_length=1)
    public_url: AnyHttpUrl
    oidc_issuer_url: AnyHttpUrl
    oidc_client_id: str = Field(min_length=1)
    oidc_scopes: tuple[str, ...] = ("openid", "profile", "email")
    oidc_client_secret: SecretStr
    session_secret: SecretStr
    owner_subjects: SecretStr
    audit_retention_days: int = Field(default=365, gt=0)

    @field_validator("oidc_scopes", mode="before")
    @classmethod
    def split_oidc_scopes(cls, value: Any) -> Any:
        """Accept the conventional space-separated OIDC scope environment value."""
        if isinstance(value, str):
            return tuple(scope for scope in value.replace(",", " ").split() if scope)
        return value

    @field_validator("oidc_client_secret", "session_secret", "owner_subjects")
    @classmethod
    def require_nonempty_secret(cls, value: SecretStr) -> SecretStr:
        """Reject accidentally empty direct secret values too."""
        if not value.get_secret_value():
            raise ValueError("must not be empty")
        return value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Use one source so direct and ``_FILE`` values cannot silently override."""
        return init_settings, _EnvironmentSource(settings_cls)

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str],
        secrets_directory: Path = SECRETS_DIRECTORY,
    ) -> Settings:
        """Construct settings from an explicit environment, primarily for tests."""
        return cls(**load_environment(environment, secrets_directory))


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide validated runtime configuration."""
    return Settings()
