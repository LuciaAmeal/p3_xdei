"""
JWT authentication utilities for mock development authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
import jwt
from config import settings


class JWTError(Exception):
    """Base exception for JWT-related errors."""
    pass


class JWTExpiredError(JWTError):
    """Raised when a JWT token has expired."""
    pass


class JWTInvalidError(JWTError):
    """Raised when a JWT token is invalid or signature verification fails."""
    pass


def generate_jwt(user_id: str) -> str:
    """
    Generate a JWT token for the given user ID.
    
    Args:
        user_id: The user identifier to encode in the token
        
    Returns:
        A signed JWT token string
        
    Raises:
        JWTError: If token generation fails
    """
    try:
        now = datetime.now(timezone.utc)
        expiration = now + timedelta(hours=settings.jwt.expiration_hours)
        
        payload = {
            'sub': user_id,
            'iat': now,
            'exp': expiration,
        }
        
        token = jwt.encode(
            payload,
            settings.jwt.secret_key,
            algorithm='HS256'
        )
        
        return token
    except Exception as e:
        raise JWTError(f"Failed to generate JWT: {str(e)}")


def validate_jwt(token: str) -> Dict:
    """
    Validate a JWT token and return its payload.
    
    Args:
        token: The JWT token string to validate
        
    Returns:
        The decoded JWT payload as a dictionary
        
    Raises:
        JWTExpiredError: If the token has expired
        JWTInvalidError: If the token signature is invalid or malformed
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key,
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise JWTExpiredError("JWT token has expired")
    except jwt.InvalidSignatureError:
        raise JWTInvalidError("JWT signature verification failed")
    except jwt.InvalidTokenError as e:
        raise JWTInvalidError(f"Invalid JWT token: {str(e)}")
    except Exception as e:
        raise JWTInvalidError(f"JWT validation failed: {str(e)}")


def get_user_id_from_jwt(token: str) -> Optional[str]:
    """
    Extract the user ID from a JWT token.
    
    Args:
        token: The JWT token string
        
    Returns:
        The user ID (subject claim), or None if extraction fails
    """
    try:
        payload = validate_jwt(token)
        return payload.get('sub')
    except JWTError:
        return None
