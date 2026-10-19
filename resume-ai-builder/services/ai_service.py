"""Optional AI provider abstraction (OpenAI-compatible chat completions).

Uses only the standard library, so no extra packages are needed. Any
OpenAI-compatible endpoint works: OpenRouter, OpenAI, and later local servers
such as Ollama (``http://localhost:11434/v1``) or LM Studio.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Dict, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, SecretStr

from utils.config import get_setting
from utils.logger import get_logger

logger = get_logger("ai")

PROVIDERS: Dict[str, Dict[str, str]] = {
    "openrouter": {"label": "OpenRouter", "base_url": "https://openrouter.ai/api/v1",
                   "env_key": "OPENROUTER_API_KEY", "default_model": "openai/gpt-4o-mini"},
    "openai": {"label": "OpenAI", "base_url": "https://api.openai.com/v1",
               "env_key": "OPENAI_API_KEY", "default_model": "gpt-4o-mini"},
    "custom": {"label": "Custom OpenAI-compatible", "base_url": "",
               "env_key": "AI_API_KEY", "default_model": ""},
}


class AIServiceError(Exception):
    """User-friendly AI failure (never contains the API key)."""


class AIConfig(BaseModel):
    provider: str = "local"
    api_key: SecretStr = SecretStr("")
    model: str = ""
    base_url: str = ""

    @property
    def is_configured(self) -> bool:
        return self.provider in PROVIDERS and bool(self.api_key.get_secret_value()) \
            and bool(self.resolved_base_url)

    @property
    def resolved_base_url(self) -> str:
        return (self.base_url or PROVIDERS.get(self.provider, {}).get("base_url", "")).rstrip("/")

    @property
    def resolved_model(self) -> str:
        return self.model or PROVIDERS.get(self.provider, {}).get("default_model", "")


def load_ai_config() -> AIConfig:
    """Build config from env / secrets. Empty values simply mean Local Mode."""
    provider = get_setting("AI_PROVIDER", "local").lower() or "local"
    if provider not in PROVIDERS:
        provider = "local"
    api_key = get_setting(PROVIDERS[provider]["env_key"]) if provider != "local" else ""
    return AIConfig(provider=provider, api_key=SecretStr(api_key),
                    model=get_setting("AI_MODEL"), base_url=get_setting("AI_BASE_URL"))


def validate_base_url(url: str) -> bool:
    """Require HTTPS, except for local model servers on localhost."""
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.netloc:
        return True
    return parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}


class AIProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, json_mode: bool = True,
                 temperature: float = 0.2) -> str:
        raise NotImplementedError


class OpenAICompatibleProvider(AIProvider):
    def __init__(self, config: AIConfig, timeout: int = 90) -> None:
        if not validate_base_url(config.resolved_base_url):
            raise AIServiceError("The AI base URL must use HTTPS (or http://localhost).")
        self._config = config
        self._timeout = timeout
        try:  # use the OS trust store when available (corporate proxies)
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            pass

    def _post(self, payload: dict) -> dict:
        request = urllib.request.Request(
            f"{self._config.resolved_base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._config.api_key.get_secret_value()}",
                "Content-Type": "application/json",
                "X-Title": "ResumeAI",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    def complete(self, system: str, user: str, json_mode: bool = True,
                 temperature: float = 0.2) -> str:
        payload = {
            "model": self._config.resolved_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            try:
                data = self._post(payload)
            except urllib.error.HTTPError as exc:
                if exc.code == 400 and json_mode:  # some providers reject response_format
                    payload.pop("response_format", None)
                    data = self._post(payload)
                else:
                    raise
            return data["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as exc:
            logger.warning("AI provider HTTP error %s", exc.code)
            if exc.code in (401, 403):
                raise AIServiceError("The AI provider rejected the API key.") from exc
            if exc.code == 429:
                raise AIServiceError("The AI provider rate limit was reached. Try again later.") from exc
            raise AIServiceError(f"The AI provider returned an error (HTTP {exc.code}).") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.warning("AI provider connection error: %s", type(exc).__name__)
            raise AIServiceError("Could not reach the AI provider.") from exc
        except (KeyError, IndexError, ValueError) as exc:
            raise AIServiceError("The AI provider returned an unexpected response.") from exc


def create_provider(config: AIConfig) -> Optional[AIProvider]:
    """Return a provider, or ``None`` when AI is not configured (Local Mode)."""
    if not config.is_configured:
        return None
    return OpenAICompatibleProvider(config)
