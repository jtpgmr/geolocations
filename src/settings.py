from __future__ import annotations
from functools import lru_cache

from pydantic import (
    Field,
    PostgresDsn,
    SecretStr,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_SETTINGS_CONFIG = SettingsConfigDict(
    extra="ignore",
    case_sensitive=False,
    env_file=".env",
    env_nested_delimiter="__",
    env_ignore_empty=True,
)


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict({**BASE_SETTINGS_CONFIG, "env_prefix": "DB__"})

    host: SecretStr
    user: SecretStr
    password: SecretStr
    database_name: SecretStr
    port: int = 5432
    driver: str | None = "asyncpg"

    @field_validator("port", mode="before")
    @classmethod
    def setDefaultPort(cls, port: object) -> object:
        return 5432 if not port else port

    @computed_field
    @property
    def dsn(self) -> str:
        return str(
            PostgresDsn.build(
                scheme=f"postgresql+{self.driver}",
                username=self.user.get_secret_value(),
                password=self.password.get_secret_value(),
                host=self.host.get_secret_value(),
                port=self.port,
                path=self.database_name.get_secret_value(),
            )
        )


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(**BASE_SETTINGS_CONFIG)

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)  # type: ignore[arg-type]


@lru_cache
def getSettings() -> AppSettings:
    return AppSettings()
