"""Typed process configuration. The launcher supplies .env to the API process."""
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore", hide_input_in_errors=True, validate_default=True
    )

    DATABASE_URL: str = "sqlite:///./ctrlz.db"
    DATA_DIR: Path = Path("./data")
    RUNBOOK_DIR: Path = Path("../runbooks")
    IMPORT_ROOT: Path = Path("../imports")
    MONITOR_INTERVAL: float = Field(default=5, ge=0.1, le=3600, allow_inf_nan=False)
    CTRLZ_OPERATOR_TOKEN: SecretStr = SecretStr("")
    CTRLZ_ALLOW_OPERATOR_TOKEN: bool = False
    CTRLZ_ALLOW_REGISTRATION: bool = True
    CTRLZ_CODE_EXECUTION_ENABLED: bool = True
    CTRLZ_DEMO_CONTROLS_ENABLED: bool = False
    CTRLZ_CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    NVIDIA_API_KEY: SecretStr = SecretStr("")
    NVIDIA_MODEL: str = Field(default="meta/llama-3.3-70b-instruct", min_length=1)
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MAX_TOKENS: int = Field(default=8192, ge=512, le=32768)
    NVIDIA_ENABLE_THINKING: bool = False
    NOTIFICATION_WEBHOOK_URL: SecretStr = SecretStr("")

    @field_validator("NVIDIA_BASE_URL")
    @classmethod
    def provider_url(cls, value):
        url = urlsplit(value)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Use an HTTP(S) API origin and path without embedded credentials")
        return value.rstrip("/")

    @field_validator("NOTIFICATION_WEBHOOK_URL")
    @classmethod
    def webhook_url(cls, value):
        if value.get_secret_value():
            url = urlsplit(value.get_secret_value())
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
                raise ValueError("Use an HTTPS webhook without embedded user credentials")
        return value

    @field_validator("CTRLZ_CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, value):
        for origin in value.split(","):
            url = urlsplit(origin.strip())
            if url.scheme not in {"http", "https"} or not url.hostname or url.path not in {"", "/"} or url.query or url.fragment or url.username or url.password:
                raise ValueError("CORS entries must be explicit HTTP(S) origins")
        return value

    @property
    def cors_origins(self):
        return [origin.strip().rstrip("/") for origin in self.CTRLZ_CORS_ORIGINS.split(",")]
