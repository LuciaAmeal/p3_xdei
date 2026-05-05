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


@dataclass
class SimulatorConfig:
    """Simulator configuration."""
    publish_interval_seconds: int
    default_speed_factor: float


@dataclass
class PredictionConfig:
    """Prediction service configuration."""
    model_path: Optional[str]
    model_version: str
    cache_ttl_seconds: int
    default_horizon_minutes: int
    history_window_days: int


@dataclass
class JWTConfig:
    """JWT authentication configuration."""
    secret_key: str
    expiration_hours: int


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

        # Simulator defaults
        self.simulator = SimulatorConfig(
            publish_interval_seconds=int(os.getenv("SIMULATOR_INTERVAL", "3")),
            default_speed_factor=float(os.getenv("SIMULATOR_SPEED_FACTOR", "1.0")),
        )

        prediction_model_path = os.getenv("PREDICTION_MODEL_PATH", "").strip() or None
        self.prediction = PredictionConfig(
            model_path=prediction_model_path,
            model_version=os.getenv("PREDICTION_MODEL_VERSION", "heuristic-v1"),
            cache_ttl_seconds=int(os.getenv("PREDICTION_CACHE_TTL_SECONDS", "900")),
            default_horizon_minutes=int(os.getenv("PREDICTION_DEFAULT_HORIZON_MINUTES", "30")),
            history_window_days=int(os.getenv("PREDICTION_HISTORY_WINDOW_DAYS", "14")),
        )
        
        # JWT Authentication
        self.jwt = JWTConfig(
            secret_key=os.getenv("JWT_SECRET_KEY", "dev-secret-key"),
            expiration_hours=int(os.getenv("JWT_EXPIRATION_HOURS", "24")),
        )
    
    def get_fiware_headers(self) -> dict:
        """Get standard FIWARE headers for API requests."""
        return {
            "Fiware-Service": self.fiware.service,
            "Fiware-ServicePath": self.fiware.servicepath,
        }


# Global settings instance
settings = Settings()

