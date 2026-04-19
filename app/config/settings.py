"""Application settings for MetaVerdax Agent."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration loaded from environment variables and .env."""

    # MCP / OpenMetadata
    openmetadata_url: str = "http://localhost:8585"
    openmetadata_token: str = ""
    openmetadata_jwt_token: str = ""
    mcp_endpoint: str = "/mcp"

    @property
    def openmetadata_auth_token(self) -> str:
        return self.openmetadata_jwt_token or self.openmetadata_token

    # LLM
    llm_provider: str = "groq"  # groq | gemini | anthropic
    llm_model: str = "llama-3.3-70b-versatile"
    groq_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""

    # MetaVerdax
    api_base_url: str = "http://127.0.0.1:8000"
    max_upload_size_mb: int = 100
    temp_upload_dir: str = "/tmp/verdax_uploads"
    reports_dir: str = "reports/agent"

    # Persistence
    sqlite_path: str = "meta_verdax_sessions.db"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "verdax"
    mongodb_scans_collection: str = "verdax_scans"

    # Risk thresholds
    critical_drift_threshold: float = 0.8
    warn_drift_threshold: float = 0.2
    critical_anomaly_rate: float = 0.15

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
