"""
Unit tests for QuantumLeap client.
"""

import json
import pytest
from unittest.mock import Mock, patch
from clients.quantumleap import (
    QuantumLeapClient,
    QuantumLeapError,
    QuantumLeapConnectionError,
    QuantumLeapNotFound,
)


@pytest.fixture
def ql_client():
    """Fixture for QuantumLeapClient instance."""
    return QuantumLeapClient(
        base_url="http://localhost:8668",
        timeout=10,
        retries=3,
        fiware_headers={"Fiware-Service": "test"},
    )


@pytest.fixture
def mock_response():
    """Fixture for mock HTTP response."""
    response = Mock()
    response.status_code = 200
    response.json.return_value = {}
    return response


class TestQuantumLeapClientBasics:
    """Test basic QuantumLeap client initialization."""
    
    def test_initialization(self, ql_client):
        """Test client initialization."""
        assert ql_client.base_url == "http://localhost:8668"
        assert ql_client.timeout == 10
        assert ql_client.retries == 3
    
    def test_url_normalization(self):
        """Test URL trailing slash removal."""
        client = QuantumLeapClient("http://localhost:8668/")
        assert client.base_url == "http://localhost:8668"


class TestQuantumLeapClientRequest:
    """Test HTTP request handling."""
    
    @patch('clients.quantumleap.requests.Session.request')
    def test_request_success(self, mock_request, ql_client, mock_response):
        """Test successful request."""
        mock_request.return_value = mock_response
        
        response = ql_client._request("GET", "/test")
        
        assert response.status_code == 200
    
    @patch('clients.quantumleap.requests.Session.request')
    def test_request_timeout(self, mock_request, ql_client):
        """Test request timeout handling."""
        import requests
        mock_request.side_effect = requests.exceptions.Timeout()
        
        with pytest.raises(QuantumLeapConnectionError):
            ql_client._request("GET", "/test")


class TestQuantumLeapClientTimeSeries:
    """Test time series queries."""
    
    @patch('clients.quantumleap.requests.Session.request')
    def test_get_time_series(self, mock_request, ql_client, mock_response):
        """Test getting time series data."""
        ts_data = {
            "id": "entity1",
            "type": "VehicleState",
            "index": ["2024-01-01T00:00:00.000", "2024-01-01T00:01:00.000"],
            "attributes": [
                {
                    "attrName": "speed",
                    "values": [10.5, 11.2],
                }
            ],
        }
        mock_response.json.return_value = ts_data
        mock_request.return_value = mock_response
        
        result = ql_client.get_time_series(
            "entity1",
            from_date="2024-01-01T00:00:00Z",
            to_date="2024-01-01T01:00:00Z",
        )
        
        assert result == ts_data
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs['params']['fromDate'] == "2024-01-01T00:00:00Z"
        assert call_kwargs['params']['toDate'] == "2024-01-01T01:00:00Z"
    
    @patch('clients.quantumleap.requests.Session.request')
    def test_get_time_series_attribute(self, mock_request, ql_client, mock_response):
        """Test getting specific attribute time series."""
        ts_data = {"attributes": [{"attrName": "speed", "values": [10.5]}]}
        mock_response.json.return_value = ts_data
        mock_request.return_value = mock_response
        
        result = ql_client.get_time_series_attribute("entity1", "speed")
        
        assert result == ts_data
        call_kwargs = mock_request.call_args[1]
        assert "speed" in call_kwargs['params']['attrs']


class TestQuantumLeapClientAvailableEntities:
    """Test available entities queries."""
    
    @patch('clients.quantumleap.requests.Session.request')
    def test_get_available_entities(self, mock_request, ql_client, mock_response):
        """Test getting available entities."""
        entities_response = {
            "entities": ["entity1", "entity2", "entity3"],
        }
        mock_response.json.return_value = entities_response
        mock_request.return_value = mock_response
        
        result = ql_client.get_available_entities()
        
        assert result == ["entity1", "entity2", "entity3"]


class TestQuantumLeapClientHealthCheck:
    """Test health check."""
    
    @patch('clients.quantumleap.requests.Session.request')
    def test_health_check_success(self, mock_request, ql_client, mock_response):
        """Test successful health check."""
        mock_request.return_value = mock_response
        
        result = ql_client.health_check()
        
        assert result is True
    
    @patch('clients.quantumleap.requests.Session.request')
    def test_health_check_failure(self, mock_request, ql_client):
        """Test failed health check."""
        import requests
        mock_request.side_effect = requests.exceptions.ConnectionError()
        
        result = ql_client.health_check()
        
        assert result is False
