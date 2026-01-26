"""Repositories package - data access layer."""

from app.repositories.analysis_repo import AnalysisRequestRepository, get_analysis_repo
from app.repositories.content_repo import ContentRepository, get_content_repo
from app.repositories.login_attempt_repo import LoginAttemptRepository, get_login_attempt_repository
from app.repositories.login_history_repo import LoginHistoryRepository, get_login_history_repository
from app.repositories.user_repo import UserRepository, get_user_repository

__all__ = [
    "AnalysisRequestRepository",
    "get_analysis_repo",
    "ContentRepository",
    "get_content_repo",
    "LoginAttemptRepository",
    "get_login_attempt_repository",
    "LoginHistoryRepository",
    "get_login_history_repository",
    "UserRepository",
    "get_user_repository",
]
