from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ticket-api"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, validation_alias="APP_DEBUG")
    api_v1_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+psycopg://ticket_user:ticket_password@localhost:5432/ticket_api"
    )
    jwt_secret_key: SecretStr
    access_token_expire_minutes: int = 30


settings = Settings()
