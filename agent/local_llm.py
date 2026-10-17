"""Thin offline client for a locally running Ollama server."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from agent.config import ollama_base_url, ollama_model, ollama_timeout_seconds


class LocalLLMError(RuntimeError):
    """Raised when the local model call fails after connectivity succeeds."""


class LocalLLMUnavailable(LocalLLMError):
    """Raised when Ollama is not reachable on the local host."""


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class LocalLLM:
    """Chat against a local Ollama instance (zero cloud)."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or ollama_base_url()).rstrip("/")
        self.model = model or ollama_model()
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else ollama_timeout_seconds()
        )

    def is_available(self) -> bool:
        try:
            self.list_models()
            return True
        except LocalLLMUnavailable:
            return False

    def list_models(self) -> list[str]:
        payload = self._request("GET", "/api/tags")
        return [m.get("name", "") for m in payload.get("models", []) if m.get("name")]

    def chat(
        self,
        messages: list[ChatMessage] | list[dict[str, str]],
        *,
        temperature: float = 0.2,
        num_predict: int = 256,
    ) -> str:
        normalized: list[dict[str, str]] = []
        for message in messages:
            if isinstance(message, ChatMessage):
                normalized.append(message.to_dict())
            else:
                normalized.append({"role": message["role"], "content": message["content"]})

        payload = self._request(
            "POST",
            "/api/chat",
            body={
                "model": self.model,
                "messages": normalized,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": num_predict,
                },
            },
        )
        content = (payload.get("message") or {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise LocalLLMError("Local model returned an empty response")
        return content.strip()

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise LocalLLMUnavailable(
                f"Ollama is unreachable at {self.base_url} ({exc})"
            ) from exc
        except TimeoutError as exc:
            raise LocalLLMUnavailable(
                f"Ollama timed out at {self.base_url}"
            ) from exc

        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise LocalLLMError("Ollama returned non-JSON") from exc
        if not isinstance(parsed, dict):
            raise LocalLLMError("Ollama returned an unexpected payload")
        return parsed
