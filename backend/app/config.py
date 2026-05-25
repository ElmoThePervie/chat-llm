from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://chatllm:chatllm@localhost:5432/chatllm"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:8000/api/auth/github/callback"

    app_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    llm_backend: str = "llama"  # llama | ollama
    llm_model_path: str = "../models/model.gguf"
    llm_mock: bool = True
    llm_n_ctx: int = 2048
    llm_max_tokens: int = 512
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "tinyllama"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
