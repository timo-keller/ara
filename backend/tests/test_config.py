from pathlib import Path

import pytest
from pydantic import ValidationError

from ara.core.config import ConfigurationError, Settings


def environment() -> dict[str, str]:
    return {
        "ARA_PUBLIC_URL": "https://ara.example.test",
        "ARA_OIDC_ISSUER_URL": "https://id.example.test/realms/ara",
        "ARA_OIDC_CLIENT_ID": "ara",
        "ARA_OIDC_CLIENT_SECRET": "oidc-secret",
        "ARA_SESSION_SECRET": "session-secret",
        "ARA_OWNER_SUBJECTS": "owner-1\nowner-2",
    }


def test_settings_load_non_sensitive_environment_values() -> None:
    values = environment() | {
        "ARA_DATABASE_URL": "sqlite+aiosqlite:////tmp/ara.db",
        "ARA_OIDC_SCOPES": "openid profile groups",
        "ARA_AUDIT_RETENTION_DAYS": "90",
    }

    settings = Settings.from_environment(values)

    assert str(settings.public_url) == "https://ara.example.test/"
    assert settings.database_url == "sqlite+aiosqlite:////tmp/ara.db"
    assert settings.oidc_scopes == ("openid", "profile", "groups")
    assert settings.audit_retention_days == 90


@pytest.mark.parametrize("value", ["", "15 15", "-1, 0"])
def test_reminder_offsets_are_validated(value: str) -> None:
    with pytest.raises(ValidationError):
        Settings.from_environment(
            environment() | {"ARA_NOTIFICATION_REMINDER_OFFSETS_MINUTES": value}
        )


def test_reminder_offsets_are_parsed_as_minutes() -> None:
    settings = Settings.from_environment(
        environment() | {"ARA_NOTIFICATION_REMINDER_OFFSETS_MINUTES": "120, 15 0"}
    )

    assert settings.notification_reminder_offsets_minutes == (120, 15, 0)


def test_secret_files_are_loaded_and_redacted(tmp_path: Path) -> None:
    for name, value in {
        "oidc": "oidc-secret\n",
        "session": "session-secret\n",
        "owners": "owner-1\nowner-2\n",
    }.items():
        (tmp_path / name).write_text(value, encoding="utf-8")
    values = environment()
    values.pop("ARA_OIDC_CLIENT_SECRET")
    values.pop("ARA_SESSION_SECRET")
    values.pop("ARA_OWNER_SUBJECTS")
    values |= {
        "ARA_OIDC_CLIENT_SECRET_FILE": "oidc",
        "ARA_SESSION_SECRET_FILE": "session",
        "ARA_OWNER_SUBJECTS_FILE": "owners",
    }

    settings = Settings.from_environment(values, tmp_path)

    assert settings.oidc_client_secret.get_secret_value() == "oidc-secret"
    assert settings.session_secret.get_secret_value() == "session-secret"
    assert settings.owner_subjects.get_secret_value() == "owner-1\nowner-2"
    assert "oidc-secret" not in repr(settings)
    assert "session-secret" not in repr(settings)
    assert "owner-1" not in repr(settings)


def test_direct_and_file_secret_values_conflict(tmp_path: Path) -> None:
    (tmp_path / "oidc").write_text("file-secret", encoding="utf-8")
    values = environment() | {"ARA_OIDC_CLIENT_SECRET_FILE": "oidc"}

    with pytest.raises(ConfigurationError, match="cannot both be set"):
        Settings.from_environment(values, tmp_path)


@pytest.mark.parametrize("filename", ["missing", "."])
def test_missing_or_unreadable_secret_file_is_clear(
    tmp_path: Path, filename: str
) -> None:
    values = environment()
    values.pop("ARA_OIDC_CLIENT_SECRET")
    values["ARA_OIDC_CLIENT_SECRET_FILE"] = filename

    with pytest.raises(ConfigurationError, match="unreadable secret file"):
        Settings.from_environment(values, tmp_path)


def test_secret_file_must_be_within_secret_directory(tmp_path: Path) -> None:
    outside_secret = tmp_path.parent / "outside-secret"
    outside_secret.write_text("secret", encoding="utf-8")
    values = environment()
    values.pop("ARA_OIDC_CLIENT_SECRET")
    values["ARA_OIDC_CLIENT_SECRET_FILE"] = str(outside_secret)

    with pytest.raises(ConfigurationError, match="must point to a file under"):
        Settings.from_environment(values, tmp_path)


def test_required_settings_are_validated() -> None:
    with pytest.raises(ValidationError, match="public_url"):
        Settings.from_environment({})


def test_backchannel_must_match_realm_path_and_owner_expression_is_validated() -> None:
    settings = Settings.from_environment(
        environment()
        | {
            "ARA_OIDC_BACKCHANNEL_URL": "http://host.docker.internal:8080/realms/ara",
            "ARA_OWNER_CLAIM_EXPRESSION": "contains(realm_access.roles, 'ara-owner')",
        }
    )
    assert (
        str(settings.oidc_backchannel_url)
        == "http://host.docker.internal:8080/realms/ara"
    )
    assert settings.owner_claim_expression is not None

    with pytest.raises(ValidationError, match="owner_claim_expression is invalid"):
        Settings.from_environment(environment() | {"ARA_OWNER_CLAIM_EXPRESSION": "("})
    with pytest.raises(ValidationError, match="issuer realm path"):
        Settings.from_environment(
            environment()
            | {"ARA_OIDC_BACKCHANNEL_URL": "http://host.docker.internal:8080/nope"}
        )
