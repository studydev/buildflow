"""Domain validation utility for internal employee email verification."""

import re
from typing import Set

# Allowed email domains for internal employees
ALLOWED_DOMAINS: Set[str] = {
    "microsoft.com",
    "github.com",
}


def normalize_email(email: str) -> str:
    """Normalize email to lowercase.
    
    Args:
        email: Email address to normalize
        
    Returns:
        Lowercase email address
    """
    return email.lower().strip()


def extract_domain(email: str) -> str:
    """Extract domain from email address.
    
    Args:
        email: Email address
        
    Returns:
        Domain part of the email (lowercase)
        
    Raises:
        ValueError: If email format is invalid
    """
    email = normalize_email(email)
    if "@" not in email:
        raise ValueError("Invalid email format: missing @")
    
    parts = email.split("@")
    if len(parts) != 2 or not parts[1]:
        raise ValueError("Invalid email format")
    
    return parts[1]


def is_allowed_domain(email: str) -> bool:
    """Check if email domain is in the allowed list.
    
    Args:
        email: Email address to check
        
    Returns:
        True if domain is allowed, False otherwise
    """
    try:
        domain = extract_domain(email)
        return domain in ALLOWED_DOMAINS
    except ValueError:
        return False


def validate_email_format(email: str) -> bool:
    """Validate email format using regex.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if format is valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_internal_email(email: str) -> tuple[bool, str]:
    """Validate that email is a valid internal employee email.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - (True, "") if valid
        - (False, error_message) if invalid
    """
    if not email:
        return False, "이메일을 입력해주세요."
    
    if not validate_email_format(email):
        return False, "올바른 이메일 형식을 입력해주세요."
    
    if not is_allowed_domain(email):
        return False, "내부 직원 전용 로그인 서비스입니다."
    
    return True, ""
