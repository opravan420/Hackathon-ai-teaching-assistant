import json
import urllib.request
import urllib.error
import socket
from .base import BaseLLMAdapter
from apps.ai_engine.exceptions import (
    LLMConnectionError,
    LLMTimeoutError,
    LLMInvalidModelError,
    LLMResponseError
)

class OllamaAdapter(BaseLLMAdapter):
    """Concrete adapter for communicating with a local Ollama HTTP API."""

    def __init__(self, api_base: str, model_tag: str, timeout: int = 120):
        self.api_base = api_base.rstrip('/')
        self.model_tag = model_tag
        self.timeout = timeout

    def generate(self, prompt: str, system_prompt: str = None, options: dict = None) -> str:
        """
        Send a generation request to the local Ollama API.
        
        Args:
            prompt: The main user prompt.
            system_prompt: Optional instructions configuring model behavior.
            options: Optional adapter-specific configuration parameters.
            
        Returns:
            The generated response string.
        """
        url = f"{self.api_base}/api/generate"
        payload = {
            "model": self.model_tag,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt
        if options:
            payload["options"] = options

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                res_body = response.read().decode('utf-8')
                res_json = json.loads(res_body)
                
                if not res_json or 'response' not in res_json:
                    raise LLMResponseError("Malformed or empty response from Ollama API.")
                
                return res_json['response']

        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise LLMInvalidModelError(f"Model '{self.model_tag}' was not found or is invalid. HTTP 404.")
            raise LLMResponseError(f"Ollama HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            if isinstance(e.reason, socket.timeout):
                raise LLMTimeoutError(f"Ollama request timed out after {self.timeout} seconds.")
            raise LLMConnectionError(f"Failed to connect to Ollama at {self.api_base}. Reason: {e.reason}")
        except socket.timeout:
            raise LLMTimeoutError(f"Ollama request timed out after {self.timeout} seconds.")
        except json.JSONDecodeError:
            raise LLMResponseError("Failed to parse JSON response from Ollama API.")
        except Exception as e:
            if "timeout" in str(e).lower():
                raise LLMTimeoutError(f"Ollama request timed out after {self.timeout} seconds.")
            raise LLMResponseError(f"Unexpected error during generation: {str(e)}")
