"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "BuildFlow API"
    app_version: str = "1.0.0"
    env: str = "development"
    debug: bool = True

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # API
    api_v1_prefix: str = "/api/v1"

    # Cosmos DB
    cosmos_connection_string: Optional[str] = None
    cosmos_database_name: str = "buildflow"

    # Cosmos DB Emulator defaults (for local development)
    # Connection string for local emulator:
    # AccountEndpoint=https://localhost:8081/;AccountKey=C2y6yDjf5/R+ob0N8A7Cgv30VRDJIWEHLM+4QDU5DE2nQ9nDuVTqobD4b8mGGyPMbIZnqyMsEcaGQy67XIw/Jw==

    # JWT Settings
    jwt_secret: Optional[str] = None  # Used with HS256 algorithm
    jwt_algorithm: str = "RS256"  # RS256 (key files) or HS256 (secret)
    jwt_private_key_path: Optional[str] = "keys/private.pem"
    jwt_public_key_path: Optional[str] = "keys/public.pem"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    # Azure OpenAI Settings
    azure_openai_endpoint: Optional[str] = "https://genai-thon-04.openai.azure.com/"
    azure_openai_api_key: Optional[str] = None
    azure_openai_deployment: str = "gpt-5.2"
    azure_openai_api_version: str = "2025-04-01-preview"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"

    # Azure AI Search Settings (Milestone 4)
    azure_search_endpoint: Optional[str] = None
    azure_search_api_key: Optional[str] = None
    azure_search_index_name: str = "buildflow-content"

    # Azure Service Bus Settings (Pipeline Infrastructure - Milestone 1)
    servicebus_connection_string: Optional[str] = None
    servicebus_namespace: Optional[str] = None
    servicebus_topic_name: str = "pipeline-triggers"

    # Pipeline Subscriptions (per design.md §6)
    servicebus_subscriptions: list[str] = [
        "analysis-sub",
        "enrichment-sub",
        "localization-sub",
        "asset-generation-sub",
        "indexing-sub",
    ]

    # Pipeline Settings
    pipeline_global_timeout_seconds: int = 600  # 10 minutes per design.md clarifications
    pipeline_max_retry_attempts: int = 3
    pipeline_retry_base_delay_seconds: int = 60

    # Azure Blob Storage Settings (Milestone 6)
    azure_storage_connection_string: Optional[str] = None
    azure_storage_account_name: Optional[str] = None
    azure_storage_account_key: Optional[str] = None
    azure_storage_cdn_host: Optional[str] = None  # e.g., "cdn.buildflow.dev"

    # Azure Communication Services Settings (OTP Email)
    acs_connection_string: Optional[str] = None
    acs_sender_address: Optional[str] = None  # e.g., "DoNotReply@<domain>.azurecomm.net"

    # GitHub Settings (for higher API rate limits)
    github_token: Optional[str] = None  # Personal Access Token for 5000 req/hour

    # OTP Settings (T035: 3-minute validity and resend limit)
    otp_ttl_minutes: int = 3  # OTP validity period
    otp_rate_limit_minutes: int = 3  # Minimum time between OTP requests

    # CORS Settings
    cors_origins: str = "http://localhost:5173,http://localhost:3000"  # Comma-separated list

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def servicebus_enabled(self) -> bool:
        """Check if Service Bus is configured."""
        return bool(self.servicebus_connection_string or self.servicebus_namespace)

    @property
    def storage_enabled(self) -> bool:
        """Check if Blob Storage is configured."""
        return bool(self.azure_storage_connection_string or self.azure_storage_account_name)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
