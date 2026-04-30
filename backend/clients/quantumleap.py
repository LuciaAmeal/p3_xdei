"""
QuantumLeap Time Series API Client.

Provides methods to query historical time series data from QuantumLeap.
Includes automatic retry logic with exponential backoff.
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from utils.logger import setup_logger

logger = setup_logger(__name__)


class QuantumLeapError(Exception):
    """Base exception for QuantumLeap client errors."""
    pass


class QuantumLeapConnectionError(QuantumLeapError):
    """Raised when connection to QuantumLeap fails."""
    pass


class QuantumLeapNotFound(QuantumLeapError):
    """Raised when requested data is not found."""
    pass


class QuantumLeapClient:
    """
    HTTP client for QuantumLeap Time Series API.
    
    Supports:
    - Historical entity queries with temporal filters
    - Time series data retrieval
    - Available entities listing
    - CrateDB backend integration
    """
    
    def __init__(
        self,
        base_url: str,
        timeout: int = 10,
        retries: int = 3,
        fiware_headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize QuantumLeap client.
        
        Args:
            base_url: Base URL for QuantumLeap (e.g., "http://localhost:8668")
            timeout: Request timeout in seconds
            retries: Number of retry attempts for failed requests
            fiware_headers: Optional FIWARE tenant headers dict
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.fiware_headers = fiware_headers or {}
        self.session = requests.Session()
    
    def _get_headers(self, content_type: str = "application/json") -> Dict[str, str]:
        """Get request headers including FIWARE tenant info."""
        headers = {
            "Content-Type": content_type,
            "Accept": "application/json",
        }
        headers.update(self.fiware_headers)
        return headers
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> requests.Response:
        """
        Perform HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: Endpoint path
            **kwargs: Additional arguments for requests.request()
        
        Returns:
            Response object
        
        Raises:
            QuantumLeapConnectionError: If connection fails
            requests.HTTPError: For HTTP errors
        """
        url = f"{self.base_url}{path}"
        
        try:
            logger.debug(f"{method} {url}")
            response = self.session.request(
                method,
                url,
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
            return response
        
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout connecting to QuantumLeap {url}: {e}")
            raise QuantumLeapConnectionError(f"Timeout: {e}") from e
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to QuantumLeap {url}: {e}")
            raise QuantumLeapConnectionError(f"Connection failed: {e}") from e
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                raise QuantumLeapNotFound(f"Data not found: {response.text}") from e
            logger.error(f"HTTP error {response.status_code}: {response.text}")
            raise
    
    def get_time_series(
        self,
        entity_id: str,
        attrs: Optional[List[str]] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get historical time series data for an entity.
        
        Args:
            entity_id: NGSI-LD entity ID
            attrs: Optional list of attribute names to retrieve
            from_date: ISO8601 start date (e.g., "2024-01-01T00:00:00Z")
            to_date: ISO8601 end date (e.g., "2024-01-31T23:59:59Z")
            limit: Maximum number of records (default: 100)
            offset: Pagination offset (default: 0)
        
        Returns:
            Time series data dict
        
        Raises:
            QuantumLeapNotFound: If entity has no historical data
            QuantumLeapError: If query fails
        """
        path = f"/v2/entities/{entity_id}"
        
        params = {
            "limit": limit,
            "offset": offset,
        }
        
        if attrs:
            params["attrs"] = ",".join(attrs)
        
        if from_date:
            params["fromDate"] = from_date
        
        if to_date:
            params["toDate"] = to_date
        
        try:
            response = self._request(
                "GET",
                path,
                headers=self._get_headers(),
                params=params,
            )
            data = response.json()
            logger.info(f"Retrieved time series for {entity_id}")
            return data
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise QuantumLeapError(f"Invalid JSON response: {e}") from e
    
    def get_time_series_attribute(
        self,
        entity_id: str,
        attr_name: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get historical time series data for a specific attribute.
        
        Args:
            entity_id: NGSI-LD entity ID
            attr_name: Attribute name (e.g., "currentPosition")
            from_date: ISO8601 start date
            to_date: ISO8601 end date
            limit: Maximum number of records
            offset: Pagination offset
        
        Returns:
            Time series data dict
        
        Raises:
            QuantumLeapNotFound: If no data available
            QuantumLeapError: If query fails
        """
        return self.get_time_series(
            entity_id,
            attrs=[attr_name],
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
    
    def get_available_entities(self) -> List[str]:
        """
        Get list of entities with available historical data.
        
        Returns:
            List of entity IDs
        
        Raises:
            QuantumLeapError: If query fails
        """
        path = "/v2/entities"
        
        try:
            response = self._request(
                "GET",
                path,
                headers=self._get_headers(),
            )
            data = response.json()
            
            # QuantumLeap returns list of entities
            entities = data.get("entities", [])
            logger.info(f"Found {len(entities)} entities with historical data")
            
            return entities
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise QuantumLeapError(f"Invalid JSON response: {e}") from e
    
    def health_check(self) -> bool:
        """
        Check if QuantumLeap is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self._request(
                "GET",
                "/version",
                headers=self._get_headers(),
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"QuantumLeap health check failed: {e}")
            return False
