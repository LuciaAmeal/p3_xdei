"""
Unit tests for health check endpoint.
"""

import pytest
import json
from unittest.mock import Mock, patch
from app import app


@pytest.fixture
def client():
    """Fixture for Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as test_client:
        yield test_client


class TestHealthEndpoint:
    """Test /health endpoint."""
    
    @patch('app.orion_client')
    @patch('app.ql_client')
    @patch('app.mqtt_client')
    def test_health_all_services_ok(self, mock_mqtt, mock_ql, mock_orion, client):
        """Test health check when all services are healthy."""
        mock_orion.health_check.return_value = True
        mock_ql.health_check.return_value = True
        mock_mqtt.is_connected = False  # Will return False after disconnect
        mock_mqtt.connect.return_value = None
        mock_mqtt.disconnect.return_value = None
        
        response = client.get('/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] in ['healthy', 'degraded']
        assert 'services' in data
        assert 'timestamp' in data
    
    @patch('app.orion_client')
    @patch('app.ql_client')
    @patch('app.mqtt_client')
    def test_health_orion_down(self, mock_mqtt, mock_ql, mock_orion, client):
        """Test health check with Orion-LD down."""
        mock_orion.health_check.return_value = False
        mock_ql.health_check.return_value = True
        mock_mqtt.is_connected = False
        mock_mqtt.connect.return_value = None
        mock_mqtt.disconnect.return_value = None
        
        response = client.get('/health')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'degraded'
        assert data['services']['orion-ld']['status'] == 'error'
    
    @patch('app.orion_client')
    @patch('app.ql_client')
    @patch('app.mqtt_client')
    def test_health_multiple_services_down(self, mock_mqtt, mock_ql, mock_orion, client):
        """Test health check with multiple services down."""
        mock_orion.health_check.return_value = False
        mock_ql.health_check.return_value = False
        mock_mqtt.is_connected = False
        mock_mqtt.connect.side_effect = Exception("Connection failed")
        
        response = client.get('/health')
        
        assert response.status_code in [200, 503]
        data = json.loads(response.data)
        assert data['status'] == 'degraded'
    
    @patch('app.orion_client')
    @patch('app.ql_client')
    @patch('app.mqtt_client')
    def test_health_response_structure(self, mock_mqtt, mock_ql, mock_orion, client):
        """Test health response has required structure."""
        mock_orion.health_check.return_value = True
        mock_ql.health_check.return_value = True
        mock_mqtt.is_connected = False
        mock_mqtt.connect.return_value = None
        mock_mqtt.disconnect.return_value = None
        
        response = client.get('/health')
        
        data = json.loads(response.data)
        assert 'status' in data
        assert 'services' in data
        assert 'timestamp' in data
        assert isinstance(data['services'], dict)


class TestPingEndpoint:
    """Test /api/ping endpoint."""
    
    def test_ping(self, client):
        """Test ping endpoint."""
        response = client.get('/api/ping')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['ping'] == 'pong'
