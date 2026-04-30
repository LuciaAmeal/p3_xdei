"""
Configuration module for XDEI backend.
Reads environment variables and provides centralized settings.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()


@dataclass
class OrionConfig:
    """Orion-LD service configuration."""
    host: str
    port: int
    timeout: int
    retries: int
    
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass
class QuantumLeapConfig:
    """QuantumLeap service configuration."""
    host: str
    port: int
    timeout: int
    retries: int
    
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


@dataclass
class MQTTConfig:
    """MQTT Broker configuration."""
    host: str
    port: int
    timeout: int
    keepalive: int


@dataclass
class CrateDBConfig:
    """CrateDB configuration (for reference)."""
    host: str
    port: int


@dataclass
class FIWAREConfig:
    """FIWARE tenant configuration."""
    service: str
    servicepath: str


@dataclass
class AppConfig:
    """Application-level configuration."""
    log_level: str
    flask_host: str
    flask_port: int
    flask_env: str


class Settings:
    """Central settings manager."""
    
    def __init__(self):
        # FIWARE tenant
        self.fiware = FIWAREConfig(
            service=os.getenv("FIWARE_SERVICE", "fiware"),
            servicepath=os.getenv("FIWARE_SERVICEPATH", "/"),
        )
        
        # Orion-LD
        self.orion = OrionConfig(
            host=os.getenv("ORION_HOST", "localhost"),
            port=int(os.getenv("ORION_PORT", "1026")),
            timeout=int(os.getenv("ORION_TIMEOUT", "10")),
            retries=int(os.getenv("ORION_RETRIES", "3")),
        )
        
        # QuantumLeap
        self.quantumleap = QuantumLeapConfig(
            host=os.getenv("QUANTUMLEAP_HOST", "localhost"),
            port=int(os.getenv("QUANTUMLEAP_PORT", "8668")),
            timeout=int(os.getenv("QUANTUMLEAP_TIMEOUT", "10")),
            retries=int(os.getenv("QUANTUMLEAP_RETRIES", "3")),
        )
        
        # MQTT
        self.mqtt = MQTTConfig(
            host=os.getenv("MQTT_HOST", "localhost"),
            port=int(os.getenv("MQTT_PORT", "1883")),
            timeout=int(os.getenv("MQTT_TIMEOUT", "5")),
            keepalive=int(os.getenv("MQTT_KEEPALIVE", "60")),
        )
        
        # CrateDB
        self.cratedb = CrateDBConfig(
            host=os.getenv("CRATEDB_HOST", "localhost"),
            port=int(os.getenv("CRATEDB_PORT", "4200")),
        )
        
        # Application
        self.app = AppConfig(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            flask_host=os.getenv("FLASK_HOST", "0.0.0.0"),
            flask_port=int(os.getenv("FLASK_PORT", "8000")),
            flask_env=os.getenv("FLASK_ENV", "development"),
        )
    
    def get_fiware_headers(self) -> dict:
        """Get standard FIWARE headers for API requests."""
        return {
            "Fiware-Service": self.fiware.service,
            "Fiware-ServicePath": self.fiware.servicepath,
        }


# Global settings instance
settings = Settings()
