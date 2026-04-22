import os
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# В контейнере рабочий каталог /app без вашего .env на диске — настройки только из env, который задаёт compose.
_in_docker = Path("/.dockerenv").exists()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None if _in_docker else ".env",
        env_file_encoding="utf-8",
        # Пустые переменные из Docker/compose не затирают дефолты (иначе APP_PORT="" роняет API).
        env_ignore_empty=True,
    )

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
    court_sync_enabled: bool = True
    court_sync_night_hour: int = 2
    court_sync_max_docs_per_run: int = 200
    court_sync_delay_sec: int = 5
    court_sync_timeout_sec: int = 60
    # Задачи в статусе running дольше N часов без завершения помечаются сбоем (зависший воркер / обрыв).
    court_sync_stale_running_hours: int = 8

    # Parser-API (kad.arbitr.ru): https://www.parser-api.com/ — заявка на ключ на сайте
    parser_api_key: str = ""
    parser_api_base_url: str = "https://parser-api.com/parser/arbitr_api"
    parser_api_timeout_sec: int = 120

    # Маршрутизация части команд через LLM + tools (см. chat_tools.py). Отключить: CHAT_TOOLS_ROUTER=0
    chat_tools_router_enabled: bool = True

    # Автосводка длинных сообщений в чат по делу (переписка юристов и т.д.). Отключить: CASE_NOTE_DIGEST=0
    case_note_digest_enabled: bool = True
    case_note_digest_min_chars: int = 200
    # ФИО через запятую — подсказка при маршрутизации документов и нескольких делах
    assistant_owner_participants: str = ""

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

    @field_validator("openai_api_key", "openai_base_url", mode="before")
    @classmethod
    def _strip_llm_strings(cls, v: object) -> object:
        if v is None or v == "":
            return v
        return str(v).strip()

    @model_validator(mode="after")
    def openai_key_from_process_env(self) -> "Settings":
        raw = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if raw and not (self.openai_api_key or "").strip():
            return self.model_copy(update={"openai_api_key": raw})
        return self

    @model_validator(mode="after")
    def chat_tools_router_from_env(self) -> "Settings":
        raw = (os.environ.get("CHAT_TOOLS_ROUTER") or "").strip().lower()
        if raw in ("0", "false", "no", "off"):
            return self.model_copy(update={"chat_tools_router_enabled": False})
        return self

    @model_validator(mode="after")
    def case_note_digest_from_env(self) -> "Settings":
        raw = (os.environ.get("CASE_NOTE_DIGEST") or "").strip().lower()
        if raw in ("0", "false", "no", "off"):
            return self.model_copy(update={"case_note_digest_enabled": False})
        return self

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
