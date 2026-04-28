"""Application configuration.

Single source of truth for all environment variables. Imports are kept light
so this module can be imported from any layer (hooks, MCP server builders,
the FastAPI app) without circular dependencies.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = Path(__file__).resolve().parent / "workspace"


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    # Anthropic
    ANTHROPIC_API_KEY: str = Field(...)

    # Postgres (read-only). Format:
    #   postgresql://user:pass@host:port/db?sslmode=require
    # The MCP container will get this via DATABASE_URI.
    READONLY_DATABASE_URL: str = Field(...)

    # FastAPI bind address.
    HOST: str = Field("127.0.0.1")
    PORT: int = Field(8080)


config = Config()  # type: ignore[call-arg]
