"""
MQTT Client for Mosquitto Broker.

Provides basic methods for connecting, disconnecting, and publishing messages.
Suitable for backend services that need to publish data or listen to events.
"""

import json
import time
from typing import Callable, Optional, Dict, Any
import paho.mqtt.client as mqtt
from utils.logger import setup_logger

logger = setup_logger(__name__)


class MQTTClientError(Exception):
    """Base exception for MQTT client errors."""
    pass


class MQTTConnectionError(MQTTClientError):
    """Raised when MQTT connection fails."""
    pass


class MQTTClient:
    """
    MQTT client for Mosquitto broker integration.
    
    Supports:
    - Publishing messages to topics
    - Subscribing to topics with callbacks (future expansion)
    - Connection management with timeouts
    - Automatic reconnection (optional)
    """
    
    # MQTT connection states
    STATE_DISCONNECTED = 0
    STATE_CONNECTING = 1
    STATE_CONNECTED = 2
    
    def __init__(
        self,
        host: str,
        port: int = 1883,
        timeout: int = 5,
        keepalive: int = 60,
        client_id: Optional[str] = None,
    ):
        """
        Initialize MQTT client.
        
        Args:
            host: MQTT broker hostname
            port: MQTT broker port (default: 1883)
            timeout: Connection timeout in seconds (default: 5)
            keepalive: Keepalive interval in seconds (default: 60)
            client_id: Optional client ID (auto-generated if not provided)
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.keepalive = keepalive
        
        # Create MQTT client
        self.client = mqtt.Client(client_id=client_id)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        
        # State tracking
        self._state = self.STATE_DISCONNECTED
        self._callbacks: Dict[str, Callable] = {}
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when client connects to broker."""
        if rc == 0:
            self._state = self.STATE_CONNECTED
            logger.info(f"Connected to MQTT broker {self.host}:{self.port}")
        else:
            logger.error(f"MQTT connection failed with code {rc}")
            self._state = self.STATE_DISCONNECTED
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when client disconnects from broker."""
        self._state = self.STATE_DISCONNECTED
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection with code {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Callback for when message is received on subscribed topic."""
        topic = msg.topic
        payload = msg.payload.decode("utf-8")
        
        logger.debug(f"Received MQTT message on {topic}")
        
        # Execute any callback whose subscription filter matches the topic.
        for topic_filter, callback in self._callbacks.items():
            if topic_filter == topic or mqtt.topic_matches_sub(topic_filter, topic):
                try:
                    callback(topic, payload)
                except Exception as e:
                    logger.error(f"Error in MQTT message callback for {topic_filter}: {e}")
    
    def _on_publish(self, client, userdata, mid):
        """Callback for when message is published."""
        logger.debug(f"MQTT message published (mid={mid})")
    
    def connect(self) -> None:
        """
        Connect to MQTT broker.
        
        Raises:
            MQTTConnectionError: If connection fails
        """
        if self._state == self.STATE_CONNECTED:
            logger.debug("Already connected to MQTT broker")
            return
        
        try:
            self._state = self.STATE_CONNECTING
            logger.info(f"Connecting to MQTT broker {self.host}:{self.port}...")
            
            self.client.connect(
                self.host,
                self.port,
                keepalive=self.keepalive,
            )
            
            # Start network loop in background
            self.client.loop_start()
            
            # Wait for connection with timeout
            start_time = time.time()
            while self._state != self.STATE_CONNECTED:
                if time.time() - start_time > self.timeout:
                    self.client.loop_stop()
                    raise MQTTConnectionError(
                        f"Connection timeout ({self.timeout}s) to {self.host}:{self.port}"
                    )
                time.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            self._state = self.STATE_DISCONNECTED
            raise MQTTConnectionError(f"Connection failed: {e}") from e
    
    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self._state == self.STATE_DISCONNECTED:
            logger.debug("Already disconnected from MQTT broker")
            return
        
        try:
            logger.info("Disconnecting from MQTT broker...")
            self.client.loop_stop()
            self.client.disconnect()
            self._state = self.STATE_DISCONNECTED
        except Exception as e:
            logger.error(f"Error during MQTT disconnect: {e}")
    
    def publish(
        self,
        topic: str,
        payload: Any,
        qos: int = 1,
    ) -> None:
        """
        Publish message to topic.
        
        Args:
            topic: MQTT topic (e.g., "vehicle/bus_1/telemetry")
            payload: Message payload (dict, str, or bytes)
                     Dicts are automatically JSON-serialized
            qos: Quality of Service level (0, 1, or 2; default: 1)
        
        Raises:
            MQTTConnectionError: If not connected
            MQTTClientError: If publish fails
        """
        if self._state != self.STATE_CONNECTED:
            raise MQTTConnectionError("Not connected to MQTT broker")
        
        try:
            # Convert payload to JSON if dict
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            
            # Convert to bytes if string
            if isinstance(payload, str):
                payload = payload.encode("utf-8")
            
            result = self.client.publish(topic, payload, qos=qos)
            
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                raise MQTTClientError(f"Publish failed with code {result.rc}")
            
            logger.debug(f"Published {len(payload)} bytes to {topic}")
        
        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")
            raise
    
    def subscribe(
        self,
        topic: str,
        callback: Callable[[str, str], None],
        qos: int = 1,
    ) -> None:
        """
        Subscribe to topic and register callback.
        
        Args:
            topic: MQTT topic pattern (e.g., "vehicle/+/telemetry")
            callback: Function to call on message (args: topic, payload)
            qos: Quality of Service level (default: 1)
        
        Raises:
            MQTTConnectionError: If not connected
            MQTTClientError: If subscription fails
        """
        if self._state != self.STATE_CONNECTED:
            raise MQTTConnectionError("Not connected to MQTT broker")
        
        try:
            result = self.client.subscribe(topic, qos=qos)
            
            if result[0] != mqtt.MQTT_ERR_SUCCESS:
                raise MQTTClientError(f"Subscribe failed with code {result[0]}")
            
            # Store callback for this topic or subscription filter.
            self._callbacks[topic] = callback
            
            logger.info(f"Subscribed to {topic}")
        
        except Exception as e:
            logger.error(f"Failed to subscribe to {topic}: {e}")
            raise
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected to broker."""
        return self._state == self.STATE_CONNECTED
    
    def __del__(self):
        """Ensure clean disconnection on object deletion."""
        if self._state == self.STATE_CONNECTED:
            try:
                self.disconnect()
            except Exception as e:
                logger.debug(f"Error during cleanup: {e}")
