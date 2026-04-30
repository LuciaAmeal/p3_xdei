"""
Orion-LD Context Broker HTTP Client.

Provides methods to interact with Orion-LD for NGSI-LD entity operations.
Includes automatic retry logic with exponential backoff and proper error handling.
"""

import json
from typing import Any, Dict, List, Optional
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from utils.logger import setup_logger

logger = setup_logger(__name__)


class OrionClientError(Exception):
    """Base exception for Orion client errors."""
    pass


class OrionConnectionError(OrionClientError):
    """Raised when connection to Orion-LD fails."""
    pass


class OrionClientNotFound(OrionClientError):
    """Raised when requested entity is not found (404)."""
    pass


class OrionClient:
    """
    HTTP client for Orion-LD Context Broker.
    
    Supports:
    - NGSI-LD entity operations (GET, POST, PATCH, DELETE)
    - Batch upsert operations
    - Query operations with filtering and pagination
    - FIWARE tenant headers (Fiware-Service, Fiware-ServicePath)
    """
    
    def __init__(
        self,
        base_url: str,
        timeout: int = 10,
        retries: int = 3,
        fiware_headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize Orion client.
        
        Args:
            base_url: Base URL for Orion-LD (e.g., "http://localhost:1026")
            timeout: Request timeout in seconds
            retries: Number of retry attempts for failed requests
            fiware_headers: Optional FIWARE tenant headers dict
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.fiware_headers = fiware_headers or {}
        self.session = requests.Session()
    
    def _get_headers(self, content_type: str = "application/ld+json") -> Dict[str, str]:
        """Get request headers including FIWARE tenant info."""
        headers = {
            "Content-Type": content_type,
            "Accept": "application/ld+json",
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
            method: HTTP method (GET, POST, PATCH, DELETE)
            path: Endpoint path (e.g., "/ngsi-ld/v1/entities")
            **kwargs: Additional arguments for requests.request()
        
        Returns:
            Response object
        
        Raises:
            OrionConnectionError: If connection fails
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
            logger.error(f"Timeout connecting to {url}: {e}")
            raise OrionConnectionError(f"Timeout: {e}") from e
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to {url}: {e}")
            raise OrionConnectionError(f"Connection failed: {e}") from e
        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                raise OrionClientNotFound(f"Entity not found: {response.text}") from e
            logger.error(f"HTTP error {response.status_code}: {response.text}")
            raise
    
    def get_entities(
        self,
        entity_type: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get entities from Orion-LD with optional filtering and pagination.
        
        Args:
            entity_type: Optional entity type to filter by
            filters: Optional dict of NGSI-LD query parameters
            limit: Maximum number of entities (default: 100)
            offset: Pagination offset (default: 0)
        
        Returns:
            List of entity dicts
        """
        path = "/ngsi-ld/v1/entities"
        params = {
            "limit": limit,
            "offset": offset,
        }
        
        if entity_type:
            params["type"] = entity_type
        
        if filters:
            params.update(filters)
        
        try:
            response = self._request(
                "GET",
                path,
                headers=self._get_headers(),
                params=params,
            )
            entities = response.json()
            logger.info(f"Retrieved {len(entities)} entities")
            return entities
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise OrionClientError(f"Invalid JSON response: {e}") from e
    
    def get_entity(self, entity_id: str) -> Dict[str, Any]:
        """
        Get a single entity by ID.
        
        Args:
            entity_id: Entity ID (e.g., "urn:ngsi-ld:GtfsRoute:route_1")
        
        Returns:
            Entity dict
        
        Raises:
            OrionClientNotFound: If entity does not exist
        """
        path = f"/ngsi-ld/v1/entities/{entity_id}"
        
        try:
            response = self._request(
                "GET",
                path,
                headers=self._get_headers(),
            )
            entity = response.json()
            logger.debug(f"Retrieved entity {entity_id}")
            return entity
        
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response: {e}")
            raise OrionClientError(f"Invalid JSON response: {e}") from e
    
    def create_entity(self, entity: Dict[str, Any]) -> str:
        """
        Create a new entity in Orion-LD.
        
        Args:
            entity: NGSI-LD entity dict (must include id, type, @context)
        
        Returns:
            Entity ID
        
        Raises:
            OrionClientError: If entity is invalid or creation fails
        """
        if "id" not in entity or "type" not in entity:
            raise OrionClientError("Entity must include 'id' and 'type'")
        
        path = "/ngsi-ld/v1/entities"
        
        try:
            response = self._request(
                "POST",
                path,
                headers=self._get_headers(),
                json=entity,
            )
            logger.info(f"Created entity {entity['id']}")
            return entity["id"]
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to create entity: {e}")
            raise OrionClientError(f"Failed to create entity: {e}") from e
    
    def update_entity(
        self,
        entity_id: str,
        attributes: Dict[str, Any],
    ) -> None:
        """
        Update entity attributes.
        
        Args:
            entity_id: Entity ID
            attributes: Dict of attributes to update
        
        Raises:
            OrionClientNotFound: If entity does not exist
            OrionClientError: If update fails
        """
        path = f"/ngsi-ld/v1/entities/{entity_id}/attrs"
        
        try:
            self._request(
                "PATCH",
                path,
                headers=self._get_headers(),
                json=attributes,
            )
            logger.info(f"Updated entity {entity_id}")
        
        except OrionClientNotFound:
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to update entity {entity_id}: {e}")
            raise OrionClientError(f"Failed to update entity: {e}") from e
    
    def batch_upsert(
        self,
        entities: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Batch upsert entities (create or update).
        
        Args:
            entities: List of NGSI-LD entity dicts
            batch_size: Size of each batch (default: 100)
        
        Returns:
            Summary dict with counts of created/updated entities
        
        Raises:
            OrionClientError: If batch operation fails
        """
        path = "/ngsi-ld/v1/entityOperations/upsert"
        
        stats = {
            "total": len(entities),
            "batches": 0,
            "errors": 0,
        }
        
        # Process in batches
        for i in range(0, len(entities), batch_size):
            batch = entities[i : i + batch_size]
            
            try:
                self._request(
                    "POST",
                    path,
                    headers=self._get_headers(),
                    json=batch,
                )
                stats["batches"] += 1
                logger.info(f"Batch {stats['batches']}: {len(batch)} entities upserted")
            
            except requests.exceptions.HTTPError as e:
                stats["errors"] += 1
                logger.error(f"Batch {stats['batches'] + 1} failed: {e}")
                # Continue with next batch instead of stopping
        
        return stats
    
    def delete_entity(self, entity_id: str) -> None:
        """
        Delete an entity.
        
        Args:
            entity_id: Entity ID
        
        Raises:
            OrionClientNotFound: If entity does not exist
            OrionClientError: If deletion fails
        """
        path = f"/ngsi-ld/v1/entities/{entity_id}"
        
        try:
            self._request(
                "DELETE",
                path,
                headers=self._get_headers(),
            )
            logger.info(f"Deleted entity {entity_id}")
        
        except OrionClientNotFound:
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"Failed to delete entity {entity_id}: {e}")
            raise OrionClientError(f"Failed to delete entity: {e}") from e
    
    def health_check(self) -> bool:
        """
        Check if Orion-LD is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self._request(
                "GET",
                "/ngsi-ld/v1/entities",
                headers=self._get_headers(),
                params={"limit": 1},
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Orion-LD health check failed: {e}")
            return False
