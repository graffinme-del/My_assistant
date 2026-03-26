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
    openai_model: str = "gpt-4.1-mini"
    owner_token: str = "owner-dev-token"
    member_token: str = "member-dev-token"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
