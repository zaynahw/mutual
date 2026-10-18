"""Environment for the local Ollama-backed agent."""

from __future__ import annotations

import os


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


def ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", "llama3.2:1b")


def ollama_timeout_seconds() -> float:
    raw = os.environ.get("OLLAMA_TIMEOUT_SECONDS", "60")
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 60.0


def prefer_local_fallback() -> bool:
    """If true, ranking/negotiate failures fall back instead of raising."""
    return os.environ.get("AGENT_LOCAL_FALLBACK", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }


def max_negotiate_rounds() -> int:
    raw = os.environ.get("AGENT_MAX_ROUNDS", "3")
    try:
        return max(1, int(raw))
    except ValueError:
        return 3
