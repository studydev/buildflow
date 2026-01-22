"""Repositories package - data access layer."""

from app.repositories.analysis_repo import AnalysisRequestRepository, get_analysis_repo
from app.repositories.asset_repo import AssetRepository, get_asset_repository
from app.repositories.content_repo import ContentRepository, get_content_repo
from app.repositories.generated_asset_repo import GeneratedAssetRepository, get_generated_asset_repo
from app.repositories.login_attempt_repo import LoginAttemptRepository, get_login_attempt_repository
from app.repositories.login_history_repo import LoginHistoryRepository, get_login_history_repository
from app.repositories.pipeline_repo import PipelineRepository, get_pipeline_repository
from app.repositories.raw_extraction_repo import RawExtractionRepository, get_raw_extraction_repository
from app.repositories.user_repo import UserRepository, get_user_repository

__all__ = [
    "AnalysisRequestRepository",
    "get_analysis_repo",
    "AssetRepository",
    "get_asset_repository",
    "ContentRepository",
    "get_content_repo",
    "GeneratedAssetRepository",
    "get_generated_asset_repo",
    "LoginAttemptRepository",
    "get_login_attempt_repository",
    "LoginHistoryRepository",
    "get_login_history_repository",
    "PipelineRepository",
    "get_pipeline_repository",
    "RawExtractionRepository",
    "get_raw_extraction_repository",
    "UserRepository",
    "get_user_repository",
]
