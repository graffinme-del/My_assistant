from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "development"
    app_port: int = 8000

    postgres_db: str = "my_assistant"
    postgres_user: str = "my_assistant"
    postgres_password: str = "change_me"
    postgres_port: int = 5432
    postgres_host: str = "postgres"

    openai_api_key: str = ""
    # База API: OpenAI по умолчанию; для OpenRouter: https://openrouter.ai/api/v1
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    # Опционально для OpenRouter (рекомендуется указать свой сайт)
    llm_http_referer: str = ""
    llm_app_title: str = "My Assistant"
    owner_token: str = "owner-dev-token"
    member_token: str = "member-dev-token"

    @field_validator("app_port", mode="before")
    @classmethod
    def _coerce_app_port(cls, v: object) -> object:
        # Docker иногда передаёт APP_PORT="" — без этого API не поднимается.
        if v == "" or v is None:
            return 8000
        return v

    @field_validator("postgres_port", mode="before")
    @classmethod
    def _coerce_postgres_port(cls, v: object) -> object:
        if v == "" or v is None:
            return 5432
        return v

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
