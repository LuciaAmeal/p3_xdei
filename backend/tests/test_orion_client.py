"""
Unit tests for Orion-LD client.
"""

import json
import pytest
from unittest.mock import Mock, patch
from clients.orion import (
    OrionClient,
    OrionClientError,
    OrionConnectionError,
    OrionClientNotFound,
)


@pytest.fixture
def orion_client():
    """Fixture for OrionClient instance."""
    return OrionClient(
        base_url="http://localhost:1026",
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


class TestOrionClientBasics:
    """Test basic Orion client initialization and configuration."""
    
    def test_initialization(self, orion_client):
        """Test client initialization."""
        assert orion_client.base_url == "http://localhost:1026"
        assert orion_client.timeout == 10
        assert orion_client.retries == 3
    
    def test_url_normalization(self):
        """Test URL trailing slash removal."""
        client = OrionClient("http://localhost:1026/")
        assert client.base_url == "http://localhost:1026"
    
    def test_fiware_headers(self, orion_client):
        """Test FIWARE header generation."""
        headers = orion_client._get_headers()
        assert "Content-Type" in headers
        assert "Accept" in headers
        assert "Fiware-Service" in headers


class TestOrionClientRequest:
    """Test HTTP request handling."""
    
    @patch('clients.orion.requests.Session.request')
    def test_request_success(self, mock_request, orion_client, mock_response):
        """Test successful request."""
        mock_request.return_value = mock_response
        
        response = orion_client._request("GET", "/test")
        
        assert response.status_code == 200
        mock_request.assert_called_once()
    
    @patch('clients.orion.requests.Session.request')
    def test_request_timeout(self, mock_request, orion_client):
        """Test request timeout handling."""
        import requests
        mock_request.side_effect = requests.exceptions.Timeout("timeout")
        
        with pytest.raises(OrionConnectionError):
            orion_client._request("GET", "/test")
    
    @patch('clients.orion.requests.Session.request')
    def test_request_connection_error(self, mock_request, orion_client):
        """Test connection error handling."""
        import requests
        mock_request.side_effect = requests.exceptions.ConnectionError("connection failed")
        
        with pytest.raises(OrionConnectionError):
            orion_client._request("GET", "/test")


class TestOrionClientEntityOperations:
    """Test entity CRUD operations."""
    
    @patch('clients.orion.requests.Session.request')
    def test_get_entities(self, mock_request, orion_client, mock_response):
        """Test getting entities."""
        entities = [{"id": "entity1", "type": "GtfsRoute"}]
        mock_response.json.return_value = entities
        mock_request.return_value = mock_response
        
        result = orion_client.get_entities(entity_type="GtfsRoute", limit=10)
        
        assert result == entities
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs['params']['type'] == "GtfsRoute"
        assert call_kwargs['params']['limit'] == 10
    
    @patch('clients.orion.requests.Session.request')
    def test_get_entity(self, mock_request, orion_client, mock_response):
        """Test getting a single entity."""
        entity = {"id": "entity1", "type": "GtfsRoute"}
        mock_response.json.return_value = entity
        mock_request.return_value = mock_response
        
        result = orion_client.get_entity("entity1")
        
        assert result == entity
    
    @patch('clients.orion.requests.Session.request')
    def test_create_entity(self, mock_request, orion_client, mock_response):
        """Test creating an entity."""
        entity = {"id": "entity1", "type": "GtfsRoute"}
        mock_request.return_value = mock_response
        
        entity_id = orion_client.create_entity(entity)
        
        assert entity_id == "entity1"
        mock_request.assert_called_once()
    
    def test_create_entity_invalid(self, orion_client):
        """Test creating entity without required fields."""
        with pytest.raises(OrionClientError):
            orion_client.create_entity({"id": "entity1"})  # Missing 'type'
    
    @patch('clients.orion.requests.Session.request')
    def test_update_entity(self, mock_request, orion_client, mock_response):
        """Test updating entity attributes."""
        mock_request.return_value = mock_response
        
        orion_client.update_entity("entity1", {"name": "Updated"})
        
        mock_request.assert_called_once()
        call_kwargs = mock_request.call_args[1]
        assert call_kwargs['json'] == {"name": "Updated"}
    
    @patch('clients.orion.requests.Session.request')
    def test_delete_entity(self, mock_request, orion_client, mock_response):
        """Test deleting an entity."""
        mock_request.return_value = mock_response
        
        orion_client.delete_entity("entity1")
        
        mock_request.assert_called_once()


class TestOrionClientBatchOperations:
    """Test batch operations."""
    
    @patch('clients.orion.requests.Session.request')
    def test_batch_upsert(self, mock_request, orion_client, mock_response):
        """Test batch upsert operation."""
        entities = [
            {"id": "entity1", "type": "GtfsRoute"},
            {"id": "entity2", "type": "GtfsRoute"},
        ]
        mock_request.return_value = mock_response
        
        result = orion_client.batch_upsert(entities, batch_size=100)
        
        assert result['total'] == 2
        assert result['batches'] == 1
        assert result['errors'] == 0
    
    @patch('clients.orion.requests.Session.request')
    def test_batch_upsert_multiple_batches(self, mock_request, orion_client, mock_response):
        """Test batch upsert with multiple batches."""
        entities = [
            {"id": f"entity{i}", "type": "GtfsRoute"}
            for i in range(250)
        ]
        mock_request.return_value = mock_response
        
        result = orion_client.batch_upsert(entities, batch_size=100)
        
        assert result['total'] == 250
        assert result['batches'] == 3
        assert mock_request.call_count == 3


class TestOrionClientHealthCheck:
    """Test health check."""
    
    @patch('clients.orion.requests.Session.request')
    def test_health_check_success(self, mock_request, orion_client, mock_response):
        """Test successful health check."""
        mock_request.return_value = mock_response
        
        result = orion_client.health_check()
        
        assert result is True
    
    @patch('clients.orion.requests.Session.request')
    def test_health_check_failure(self, mock_request, orion_client):
        """Test failed health check."""
        import requests
        mock_request.side_effect = requests.exceptions.ConnectionError()
        
        result = orion_client.health_check()
        
        assert result is False
