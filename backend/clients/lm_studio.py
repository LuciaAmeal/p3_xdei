import requests
from typing import List, Dict, Any, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)

class LMStudioError(Exception):
    """Base exception for LM Studio client errors."""
    pass

class LMStudioClient:
    """Client for interacting with LM Studio API (OpenAI compatible)."""

    def __init__(self, base_url: str, timeout: int = 60):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout

    def chat_completion(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a chat completion from LM Studio.
        
        Args:
            messages: List of message objects with 'role' and 'content'.
            model: Optional model name. If not provided, LM Studio uses the currently loaded model.
            
        Returns:
            The completion response from LM Studio.
        """
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "messages": messages,
            "temperature": 0.7,
            "stream": False
        }
        
        if model:
            payload["model"] = model

        try:
            logger.info(f"Sending chat completion request to LM Studio at {url}")
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"LM Studio API request failed: {str(e)}")
            raise LMStudioError(f"Failed to connect to LM Studio: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in LM Studio client: {str(e)}")
            raise LMStudioError(f"Unexpected error: {str(e)}")

    def health_check(self) -> bool:
        """Check if LM Studio is reachable."""
        try:
            # Try to get the models list as a health check
            url = f"{self.base_url}/v1/models"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False
