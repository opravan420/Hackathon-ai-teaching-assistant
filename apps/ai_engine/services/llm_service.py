import os
import urllib.request
import urllib.error
import json
import socket
from apps.ai_engine.adapters.ollama import OllamaAdapter

class LLMService:
    """Application-level service wrapping the configured LLM adapter."""

    def __init__(self):
        self.api_base = os.getenv('OLLAMA_API_BASE', 'http://localhost:11434').rstrip('/')
        self.model_tag = os.getenv('OLLAMA_MODEL_TAG', 'gemma3:4b')
        timeout_str = os.getenv('OLLAMA_TIMEOUT_SECONDS', '120')
        try:
            self.timeout = int(timeout_str)
        except ValueError:
            self.timeout = 120

        self.adapter = OllamaAdapter(
            api_base=self.api_base,
            model_tag=self.model_tag,
            timeout=self.timeout
        )

    def generate_text(self, prompt: str, system_prompt: str = None, options: dict = None) -> str:
        """Forwards text generation requests to the concrete adapter."""
        return self.adapter.generate(prompt, system_prompt, options)

    def perform_health_check(self) -> dict:
        """
        Runs a lightweight infrastructure health check without performing inference.
        
        Returns:
            A status dictionary detailing Ollama and model availability.
        """
        status = {
            "ollama_status": "UNAVAILABLE",
            "model_status": "UNKNOWN",
            "model_tag": self.model_tag,
            "api_base": self.api_base,
            "reason": None
        }

        url = f"{self.api_base}/api/tags"
        try:
            req = urllib.request.Request(url)
            # Short 5s timeout for health checks
            with urllib.request.urlopen(req, timeout=5) as response:
                res_body = response.read().decode('utf-8')
                data = json.loads(res_body)
                status["ollama_status"] = "AVAILABLE"

                models = data.get("models", [])
                model_names = [m.get("name") for m in models]

                if self.model_tag in model_names:
                    status["model_status"] = "READY"
                else:
                    status["model_status"] = "MISSING"
                    status["reason"] = f"Configured model '{self.model_tag}' is not installed."

        except urllib.error.URLError as e:
            if isinstance(e.reason, socket.timeout):
                status["reason"] = "Connection timed out"
            else:
                status["reason"] = f"Connection refused: {str(e.reason)}"
        except socket.timeout:
            status["reason"] = "Connection timed out"
        except json.JSONDecodeError:
            status["reason"] = "Malformed tags response body"
        except Exception as e:
            status["reason"] = f"Unexpected health check error: {str(e)}"

        return status
