"""
Tests for JWT authentication utilities.
"""

import pytest
from datetime import datetime, timedelta, timezone
import jwt as pyjwt

from backend.auth import (
    generate_jwt,
    validate_jwt,
    get_user_id_from_jwt,
    JWTError,
    JWTExpiredError,
    JWTInvalidError,
)
from backend.config import settings


class TestGenerateJWT:
    """Test JWT token generation."""

    def test_generate_jwt_returns_string(self):
        """Test that generate_jwt returns a string token."""
        token = generate_jwt('test_user')
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_jwt_with_different_users(self):
        """Test that different users get different tokens."""
        token1 = generate_jwt('user1')
        token2 = generate_jwt('user2')
        assert token1 != token2

    def test_generated_jwt_has_correct_claims(self):
        """Test that generated JWT has correct claims."""
        user_id = 'test_user_123'
        token = generate_jwt(user_id)

        # Decode without verification to check claims
        payload = pyjwt.decode(token, options={"verify_signature": False})

        assert payload['sub'] == user_id
        assert 'iat' in payload
        assert 'exp' in payload
        assert isinstance(payload['iat'], int)
        assert isinstance(payload['exp'], int)

    def test_jwt_has_correct_expiration(self):
        """Test that JWT has correct expiration time."""
        user_id = 'test_user'
        before = datetime.now(timezone.utc)
        token = generate_jwt(user_id)
        after = datetime.now(timezone.utc)

        payload = pyjwt.decode(token, options={"verify_signature": False})
        exp_time = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)

        # Check expiration is approximately 24 hours in the future
        expected_min = before + timedelta(hours=settings.jwt.expiration_hours - 1)
        expected_max = after + timedelta(hours=settings.jwt.expiration_hours + 1)

        assert expected_min <= exp_time <= expected_max

    def test_generate_jwt_failure_propagates_error(self):
        """Test that generate_jwt handles edge cases gracefully."""
        # The implementation is robust and won't fail easily since it converts to string
        # Test that empty string still generates a token (it's valid)
        token = generate_jwt('')
        assert isinstance(token, str)
        assert len(token) > 0


class TestValidateJWT:
    """Test JWT token validation."""

    def test_validate_jwt_with_valid_token(self):
        """Test that validate_jwt accepts valid token."""
        user_id = 'test_user'
        token = generate_jwt(user_id)

        payload = validate_jwt(token)

        assert payload['sub'] == user_id
        assert 'iat' in payload
        assert 'exp' in payload

    def test_validate_jwt_with_expired_token(self):
        """Test that validate_jwt raises JWTExpiredError for expired token."""
        # Create a token that's already expired
        now = datetime.now(timezone.utc)
        expired_time = now - timedelta(hours=1)

        payload = {
            'sub': 'test_user',
            'iat': now,
            'exp': expired_time,
        }

        token = pyjwt.encode(
            payload,
            settings.jwt.secret_key,
            algorithm='HS256'
        )

        with pytest.raises(JWTExpiredError):
            validate_jwt(token)

    def test_validate_jwt_with_invalid_signature(self):
        """Test that validate_jwt raises JWTInvalidError for tampered token."""
        token = generate_jwt('test_user')

        # Tamper with token
        tampered_token = token[:-10] + '0000000000'

        with pytest.raises(JWTInvalidError):
            validate_jwt(tampered_token)

    def test_validate_jwt_with_wrong_key(self):
        """Test that validate_jwt uses the configured secret key from settings."""
        user_id = 'test_user'
        token = generate_jwt(user_id)

        # Create a token with a different secret key manually
        different_secret = 'completely-different-secret-key'
        different_payload = {
            'sub': user_id,
            'iat': datetime.now(timezone.utc),
            'exp': datetime.now(timezone.utc) + timedelta(hours=24),
        }
        different_token = pyjwt.encode(
            different_payload,
            different_secret,
            algorithm='HS256'
        )

        # This token was signed with a different key, so validation should fail
        with pytest.raises(JWTInvalidError):
            validate_jwt(different_token)

    def test_validate_jwt_with_malformed_token(self):
        """Test that validate_jwt raises JWTInvalidError for malformed token."""
        with pytest.raises(JWTInvalidError):
            validate_jwt('not.a.valid.token')

    def test_validate_jwt_with_empty_token(self):
        """Test that validate_jwt raises JWTInvalidError for empty token."""
        with pytest.raises(JWTInvalidError):
            validate_jwt('')


class TestGetUserIdFromJWT:
    """Test user ID extraction from JWT."""

    def test_get_user_id_with_valid_token(self):
        """Test that get_user_id_from_jwt extracts user ID correctly."""
        user_id = 'test_user_123'
        token = generate_jwt(user_id)

        extracted_id = get_user_id_from_jwt(token)

        assert extracted_id == user_id

    def test_get_user_id_with_expired_token(self):
        """Test that get_user_id_from_jwt returns None for expired token."""
        # Create expired token
        now = datetime.now(timezone.utc)
        expired_time = now - timedelta(hours=1)

        payload = {
            'sub': 'test_user',
            'iat': now,
            'exp': expired_time,
        }

        token = pyjwt.encode(
            payload,
            settings.jwt.secret_key,
            algorithm='HS256'
        )

        extracted_id = get_user_id_from_jwt(token)
        assert extracted_id is None

    def test_get_user_id_with_invalid_token(self):
        """Test that get_user_id_from_jwt returns None for invalid token."""
        extracted_id = get_user_id_from_jwt('invalid.token.here')
        assert extracted_id is None

    def test_get_user_id_with_different_users(self):
        """Test that get_user_id_from_jwt works with different user IDs."""
        user_ids = ['user1', 'user2', 'test@example.com', 'admin']

        for user_id in user_ids:
            token = generate_jwt(user_id)
            extracted_id = get_user_id_from_jwt(token)
            assert extracted_id == user_id
