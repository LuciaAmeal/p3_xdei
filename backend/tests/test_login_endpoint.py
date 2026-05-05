"""
Tests for login endpoint.
"""

import pytest
import json
from unittest.mock import patch
from app import app
from auth import validate_jwt


@pytest.fixture
def client():
    """Fixture for Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as test_client:
        yield test_client


class TestLoginEndpoint:
    """Test POST /api/login endpoint."""

    def test_login_with_valid_credentials(self, client):
        """Test login with valid username and password."""
        response = client.post(
            '/api/login',
            data=json.dumps({
                'username': 'test_user',
                'password': 'test_password'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        
        assert 'token' in data
        assert 'user_id' in data
        assert 'expires_in_hours' in data
        assert data['user_id'] == 'test_user'
        assert data['expires_in_hours'] == 24

    def test_login_token_is_valid_jwt(self, client):
        """Test that login returns a valid JWT token."""
        response = client.post(
            '/api/login',
            data=json.dumps({
                'username': 'jwt_test',
                'password': 'any_password'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        token = data['token']

        # Validate that token is a valid JWT
        payload = validate_jwt(token)
        assert payload['sub'] == 'jwt_test'

    def test_login_with_different_users(self, client):
        """Test login creates different tokens for different users."""
        users = ['user1', 'user2', 'alice', 'bob']

        for username in users:
            response = client.post(
                '/api/login',
                data=json.dumps({
                    'username': username,
                    'password': 'password'
                }),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['user_id'] == username

            # Verify token contains correct user ID
            payload = validate_jwt(data['token'])
            assert payload['sub'] == username

    def test_login_with_empty_username(self, client):
        """Test login rejects empty username."""
        response = client.post(
            '/api/login',
            data=json.dumps({
                'username': '',
                'password': 'test_password'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_login_with_empty_password(self, client):
        """Test login rejects empty password."""
        response = client.post(
            '/api/login',
            data=json.dumps({
                'username': 'test_user',
                'password': ''
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_login_with_missing_username(self, client):
        """Test login rejects request without username."""
        response = client.post(
            '/api/login',
            data=json.dumps({
                'password': 'test_password'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_login_with_missing_password(self, client):
        """Test login rejects request without password."""
        response = client.post(
            '/api/login',
            data=json.dumps({
                'username': 'test_user'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_login_with_whitespace_only_username(self, client):
        """Test login rejects whitespace-only username."""
        response = client.post(
            '/api/login',
            data=json.dumps({
                'username': '   ',
                'password': 'test_password'
            }),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_login_with_empty_json_body(self, client):
        """Test login with empty JSON body."""
        response = client.post(
            '/api/login',
            data=json.dumps({}),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_login_with_no_content_type(self, client):
        """Test login without JSON content type."""
        response = client.post(
            '/api/login',
            data='invalid'
        )

        assert response.status_code in [400, 415]  # Bad request or unsupported media type

    def test_login_with_special_characters_in_username(self, client):
        """Test login with special characters in username."""
        usernames = ['user@example.com', 'user-123', 'user_test', 'user.name']

        for username in usernames:
            response = client.post(
                '/api/login',
                data=json.dumps({
                    'username': username,
                    'password': 'password'
                }),
                content_type='application/json'
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['user_id'] == username

    def test_login_response_has_correct_headers(self, client):
        """Test that login response has correct headers."""
        response = client.post(
            '/api/login',
            data=json.dumps({
                'username': 'test',
                'password': 'test'
            }),
            content_type='application/json'
        )

        assert response.status_code == 200
        assert response.content_type == 'application/json'

    def test_login_cors_headers(self, client):
        """Test that login response includes CORS headers."""
        response = client.post(
            '/api/login',
            data=json.dumps({
                'username': 'test',
                'password': 'test'
            }),
            content_type='application/json'
        )

        assert 'Access-Control-Allow-Origin' in response.headers
        assert response.headers['Access-Control-Allow-Origin'] == '*'
