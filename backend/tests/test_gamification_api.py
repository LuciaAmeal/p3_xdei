from __future__ import annotations

from unittest.mock import patch

from clients.orion import OrionClientNotFound
from app import app


def _make_user_profile_entity(user_id: str = 'alice', points: int = 20, visited_stops=None, achievements=None, redeemed_discounts=None):
    return {
        'id': f'urn:ngsi-ld:UserProfile:{user_id}',
        'type': 'UserProfile',
        'displayName': {'type': 'Property', 'value': 'Alice'},
        'totalPoints': {'type': 'Property', 'value': points},
        'visitedStops': {'type': 'Property', 'value': visited_stops or []},
        'achievements': {'type': 'Property', 'value': achievements or []},
        'lastActivityAt': {'type': 'Property', 'value': '2026-05-05T10:00:00Z'},
        'redeemedDiscounts': {'type': 'Property', 'value': redeemed_discounts or []},
    }


@patch('app.orion_client')
def test_api_user_profile_returns_profile_for_authenticated_user(mock_orion):
    mock_orion.get_entity.return_value = _make_user_profile_entity(visited_stops=['urn:ngsi-ld:GtfsStop:s1'])

    app.config['TESTING'] = True
    with app.test_client() as client:
        response = client.get('/api/user/alice/profile', headers={'X-User-Id': 'alice'})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['userId'] == 'alice'
    assert payload['totalPoints'] == 20
    assert payload['visitedStops'] == ['urn:ngsi-ld:GtfsStop:s1']
    mock_orion.get_entity.assert_called_once_with('urn:ngsi-ld:UserProfile:alice')


@patch('app.orion_client')
def test_api_user_profile_rejects_mismatched_identity(mock_orion):
    app.config['TESTING'] = True
    with app.test_client() as client:
        response = client.get('/api/user/alice/profile', headers={'X-User-Id': 'bob'})

    assert response.status_code == 403
    payload = response.get_json()
    assert 'error' in payload
    mock_orion.get_entity.assert_not_called()


@patch('app.orion_client')
def test_api_user_record_trip_updates_points_and_stops(mock_orion):
    mock_orion.get_entity.return_value = _make_user_profile_entity(points=5, visited_stops=[])

    app.config['TESTING'] = True
    with app.test_client() as client:
        response = client.post(
            '/api/user/record-trip',
            headers={'X-User-Id': 'alice', 'X-User-Name': 'Alice'},
            json={'tripId': 'urn:ngsi-ld:GtfsTrip:t1', 'stopId': 'urn:ngsi-ld:GtfsStop:s1'},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['userId'] == 'alice'
    assert payload['totalPoints'] == 20
    assert payload['visitedStops'] == ['urn:ngsi-ld:GtfsStop:s1']
    assert payload['lastActivityAt'].endswith('Z')
    mock_orion.update_entity.assert_called_once()


@patch('app.orion_client')
def test_api_user_redeem_creates_redemption_and_deducts_points(mock_orion):
    mock_orion.get_entity.return_value = _make_user_profile_entity(points=20, visited_stops=['urn:ngsi-ld:GtfsStop:s1'])

    app.config['TESTING'] = True
    with app.test_client() as client:
        response = client.post(
            '/api/user/redeem',
            headers={'X-User-Id': 'alice', 'X-User-Name': 'Alice'},
            json={
                'discountCode': 'BUS10',
                'discountValue': 10,
                'pointsCost': 12,
                'validUntil': '2026-06-01T00:00:00Z',
            },
        )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload['profile']['totalPoints'] == 8
    assert payload['redemption']['discountCode'] == 'BUS10'
    assert payload['redemption']['status'] == 'redeemed'
    mock_orion.create_entity.assert_called_once()
    mock_orion.update_entity.assert_called_once()


@patch('app.orion_client')
def test_api_user_redeem_rejects_insufficient_points(mock_orion):
    mock_orion.get_entity.return_value = _make_user_profile_entity(points=5)

    app.config['TESTING'] = True
    with app.test_client() as client:
        response = client.post(
            '/api/user/redeem',
            headers={'X-User-Id': 'alice'},
            json={'discountCode': 'BUS10', 'pointsCost': 12},
        )

    assert response.status_code == 409
    payload = response.get_json()
    assert 'error' in payload
    mock_orion.update_entity.assert_not_called()
    mock_orion.create_entity.assert_not_called()


@patch('app.orion_client')
def test_api_user_profile_returns_404_when_missing(mock_orion):
    mock_orion.get_entity.side_effect = OrionClientNotFound('missing')

    app.config['TESTING'] = True
    with app.test_client() as client:
        response = client.get('/api/user/alice/profile', headers={'X-User-Id': 'alice'})

    assert response.status_code == 404
    payload = response.get_json()


# JWT Authentication Tests

@patch('app.orion_client')
def test_api_user_profile_rejects_missing_auth_headers(mock_orion):
    """Test that profile endpoint rejects requests without authentication."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        response = client.get('/api/user/alice/profile')

    # Should get 401/403 without any auth header
    assert response.status_code in [401, 403]
    payload = response.get_json()
    assert 'error' in payload


@patch('app.orion_client')
def test_api_user_profile_accepts_valid_jwt_token(mock_orion):
    """Test that profile endpoint accepts valid JWT token."""
    from auth import generate_jwt

    mock_orion.get_entity.return_value = _make_user_profile_entity(
        user_id='alice',
        points=20,
        visited_stops=['urn:ngsi-ld:GtfsStop:s1']
    )

    app.config['TESTING'] = True
    with app.test_client() as client:
        token = generate_jwt('alice')
        response = client.get(
            '/api/user/alice/profile',
            headers={'Authorization': f'Bearer {token}'}
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['userId'] == 'alice'
    assert payload['totalPoints'] == 20


@patch('app.orion_client')
def test_api_user_profile_rejects_invalid_jwt_token(mock_orion):
    """Test that profile endpoint rejects invalid JWT token."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        response = client.get(
            '/api/user/alice/profile',
            headers={'Authorization': 'Bearer invalid.token.here'}
        )

    assert response.status_code in [401, 403]
    mock_orion.get_entity.assert_not_called()


@patch('app.orion_client')
def test_api_user_record_trip_accepts_jwt_token(mock_orion):
    """Test that record-trip endpoint accepts valid JWT token."""
    from auth import generate_jwt

    mock_orion.get_entity.return_value = _make_user_profile_entity(points=5, visited_stops=[])

    app.config['TESTING'] = True
    with app.test_client() as client:
        token = generate_jwt('alice')
        response = client.post(
            '/api/user/record-trip',
            headers={'Authorization': f'Bearer {token}', 'X-User-Name': 'Alice'},
            json={'tripId': 'urn:ngsi-ld:GtfsTrip:t1', 'stopId': 'urn:ngsi-ld:GtfsStop:s1'},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['userId'] == 'alice'


@patch('app.orion_client')
def test_api_user_redeem_accepts_jwt_token(mock_orion):
    """Test that redeem endpoint accepts valid JWT token."""
    from auth import generate_jwt

    mock_orion.get_entity.return_value = _make_user_profile_entity(
        points=20,
        visited_stops=['urn:ngsi-ld:GtfsStop:s1']
    )

    app.config['TESTING'] = True
    with app.test_client() as client:
        token = generate_jwt('alice')
        response = client.post(
            '/api/user/redeem',
            headers={'Authorization': f'Bearer {token}', 'X-User-Name': 'Alice'},
            json={
                'discountCode': 'BUS10',
                'discountValue': 10,
                'pointsCost': 12,
                'validUntil': '2026-06-01T00:00:00Z',
            },
        )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload['profile']['totalPoints'] == 8


@patch('app.orion_client')
def test_api_user_profile_backward_compatibility_x_user_id(mock_orion):
    """Test that profile endpoint still accepts X-User-Id header (backward compatibility)."""
    mock_orion.get_entity.return_value = _make_user_profile_entity(
        user_id='bob',
        points=15,
        visited_stops=['urn:ngsi-ld:GtfsStop:s2']
    )

    app.config['TESTING'] = True
    with app.test_client() as client:
        response = client.get(
            '/api/user/bob/profile',
            headers={'X-User-Id': 'bob'}
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['userId'] == 'bob'
    assert payload['totalPoints'] == 15

    assert payload['error'] == 'User profile not found'