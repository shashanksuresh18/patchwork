from functools import lru_cache
from pathlib import Path

from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
    )

    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key"),
    )
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
    )
    google_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "google_api_key"),
    )
    langfuse_public_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LANGFUSE_PUBLIC_KEY", "langfuse_public_key"),
    )
    langfuse_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LANGFUSE_SECRET_KEY", "langfuse_secret_key"),
    )
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_HOST", "langfuse_host"),
    )
    claude_model: str = Field(
        default="claude-sonnet-4-6",
        validation_alias=AliasChoices("PATCHWORK_CLAUDE_MODEL", "claude_model"),
    )
    openai_model: str = Field(
        default="gpt-4o",
        validation_alias=AliasChoices("PATCHWORK_OPENAI_MODEL", "openai_model"),
    )
    gemini_model: str = Field(
        default="gemini-1.5-pro",
        validation_alias=AliasChoices("PATCHWORK_GEMINI_MODEL", "gemini_model"),
    )
    plan_dir: Path = Field(
        default=Path(".patchwork/plans"),
        validation_alias=AliasChoices("PATCHWORK_PLAN_DIR", "plan_dir"),
    )
    default_backend: str = Field(
        default="claude",
        validation_alias=AliasChoices("PATCHWORK_DEFAULT_BACKEND", "default_backend"),
    )
    use_cli_backends: bool = Field(
        default=True,
        validation_alias=AliasChoices("PATCHWORK_USE_CLI_BACKENDS", "use_cli_backends"),
    )
    claude_cli_command: str = Field(
        default="claude -p",
        validation_alias=AliasChoices("PATCHWORK_CLAUDE_CLI_COMMAND", "claude_cli_command"),
    )
    codex_cli_command: str = Field(
        default="codex exec",
        validation_alias=AliasChoices("PATCHWORK_CODEX_CLI_COMMAND", "codex_cli_command"),
    )
    gemini_cli_command: str = Field(
        default="gemini -p",
        validation_alias=AliasChoices("PATCHWORK_GEMINI_CLI_COMMAND", "gemini_cli_command"),
    )
    agent_cli_timeout: int = Field(
        default=7200,
        validation_alias=AliasChoices("PATCHWORK_AGENT_CLI_TIMEOUT", "agent_cli_timeout"),
    )
    debug_prompt: bool = Field(
        default=False,
        validation_alias=AliasChoices("PATCHWORK_DEBUG_PROMPT", "debug_prompt"),
    )
    caveman_mode: bool = Field(
        default=False,
        validation_alias=AliasChoices("PATCHWORK_CAVEMAN_MODE", "caveman_mode"),
    )
    use_graphifyy: bool = Field(
        default=False,
        validation_alias=AliasChoices("PATCHWORK_USE_GRAPHIFYY", "use_graphifyy"),
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    return Settings()
