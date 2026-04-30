"""
Unit tests for MQTT client.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
import paho.mqtt.client as mqtt
from clients.mqtt import (
    MQTTClient,
    MQTTClientError,
    MQTTConnectionError,
)


@pytest.fixture
def mqtt_client():
    """Fixture for MQTTClient instance."""
    return MQTTClient(
        host="localhost",
        port=1883,
        timeout=5,
        keepalive=60,
    )


class TestMQTTClientBasics:
    """Test basic MQTT client initialization."""
    
    def test_initialization(self, mqtt_client):
        """Test client initialization."""
        assert mqtt_client.host == "localhost"
        assert mqtt_client.port == 1883
        assert mqtt_client.timeout == 5
        assert mqtt_client.keepalive == 60
    
    def test_is_connected_initial(self, mqtt_client):
        """Test initial connection state."""
        assert mqtt_client.is_connected is False


class TestMQTTClientConnection:
    """Test connection management."""
    
    @patch('clients.mqtt.mqtt.Client')
    def test_connect_success(self, mock_mqtt_client_class, mqtt_client):
        """Test successful connection."""
        mock_mqtt = Mock()
        mock_mqtt_client_class.return_value = mock_mqtt
        
        # Simulate successful connection
        mqtt_client.client = mock_mqtt
        mqtt_client._on_connect(mock_mqtt, None, None, 0)
        
        assert mqtt_client._state == mqtt_client.STATE_CONNECTED
    
    @patch('clients.mqtt.mqtt.Client')
    def test_disconnect(self, mock_mqtt_client_class, mqtt_client):
        """Test disconnection."""
        mock_mqtt = Mock()
        mqtt_client.client = mock_mqtt
        
        # Set to connected first
        mqtt_client._state = mqtt_client.STATE_CONNECTED
        
        # Disconnect
        mqtt_client._on_disconnect(mock_mqtt, None, 0)
        
        assert mqtt_client._state == mqtt_client.STATE_DISCONNECTED


class TestMQTTClientPublish:
    """Test message publishing."""
    
    def test_publish_not_connected(self, mqtt_client):
        """Test publishing when not connected."""
        mqtt_client._state = mqtt_client.STATE_DISCONNECTED
        
        with pytest.raises(MQTTConnectionError):
            mqtt_client.publish("test/topic", "message")
    
    @patch('clients.mqtt.mqtt.Client')
    def test_publish_string(self, mock_mqtt_class, mqtt_client):
        """Test publishing string message."""
        mock_mqtt = Mock()
        mock_publish = Mock()
        mock_publish.rc = mqtt.MQTT_ERR_SUCCESS
        mock_mqtt.publish.return_value = mock_publish
        mqtt_client.client = mock_mqtt
        
        mqtt_client._state = mqtt_client.STATE_CONNECTED
        mqtt_client.publish("test/topic", "message")
        
        mock_mqtt.publish.assert_called_once()
        call_args = mock_mqtt.publish.call_args
        assert call_args[0][0] == "test/topic"
        assert call_args[0][1] == b"message"
    
    @patch('clients.mqtt.mqtt.Client')
    def test_publish_dict(self, mock_mqtt_class, mqtt_client):
        """Test publishing dict message (JSON serialized)."""
        mock_mqtt = Mock()
        mock_publish = Mock()
        mock_publish.rc = mqtt.MQTT_ERR_SUCCESS
        mock_mqtt.publish.return_value = mock_publish
        mqtt_client.client = mock_mqtt
        
        mqtt_client._state = mqtt_client.STATE_CONNECTED
        payload = {"key": "value"}
        mqtt_client.publish("test/topic", payload)
        
        mock_mqtt.publish.assert_called_once()
        call_args = mock_mqtt.publish.call_args
        # Check JSON encoding
        published_payload = call_args[0][1]
        assert json.loads(published_payload) == payload
    
    @patch('clients.mqtt.mqtt.Client')
    def test_publish_bytes(self, mock_mqtt_class, mqtt_client):
        """Test publishing bytes message."""
        mock_mqtt = Mock()
        mock_publish = Mock()
        mock_publish.rc = mqtt.MQTT_ERR_SUCCESS
        mock_mqtt.publish.return_value = mock_publish
        mqtt_client.client = mock_mqtt
        
        mqtt_client._state = mqtt_client.STATE_CONNECTED
        mqtt_client.publish("test/topic", b"bytes")
        
        mock_mqtt.publish.assert_called_once()


class TestMQTTClientSubscribe:
    """Test message subscription."""
    
    def test_subscribe_not_connected(self, mqtt_client):
        """Test subscribing when not connected."""
        mqtt_client._state = mqtt_client.STATE_DISCONNECTED
        
        def callback(topic, payload):
            pass
        
        with pytest.raises(MQTTConnectionError):
            mqtt_client.subscribe("test/topic", callback)
    
    @patch('clients.mqtt.mqtt.Client')
    def test_subscribe_success(self, mock_mqtt_class, mqtt_client):
        """Test successful subscription."""
        mock_mqtt = Mock()
        mock_subscribe = Mock()
        mock_subscribe.__getitem__ = Mock(return_value=mqtt.MQTT_ERR_SUCCESS)
        mock_mqtt.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
        mqtt_client.client = mock_mqtt
        
        mqtt_client._state = mqtt_client.STATE_CONNECTED
        
        def callback(topic, payload):
            pass
        
        mqtt_client.subscribe("test/topic", callback)
        
        assert "test/topic" in mqtt_client._callbacks
        assert mqtt_client._callbacks["test/topic"] == callback


class TestMQTTClientCallbacks:
    """Test message callbacks."""
    
    def test_on_message_with_callback(self, mqtt_client):
        """Test message callback execution."""
        callback_called = {"called": False, "args": None}
        
        def test_callback(topic, payload):
            callback_called["called"] = True
            callback_called["args"] = (topic, payload)
        
        mqtt_client._callbacks["test/topic"] = test_callback
        
        # Create mock message
        mock_msg = Mock()
        mock_msg.topic = "test/topic"
        mock_msg.payload = b"test payload"
        
        mqtt_client._on_message(None, None, mock_msg)
        
        assert callback_called["called"] is True
        assert callback_called["args"] == ("test/topic", "test payload")
    
    def test_on_connect_success(self, mqtt_client):
        """Test on_connect callback with success."""
        mqtt_client._on_connect(None, None, None, 0)
        assert mqtt_client._state == mqtt_client.STATE_CONNECTED
    
    def test_on_connect_failure(self, mqtt_client):
        """Test on_connect callback with failure."""
        mqtt_client._on_connect(None, None, None, 1)
        assert mqtt_client._state == mqtt_client.STATE_DISCONNECTED
