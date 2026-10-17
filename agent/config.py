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
    """If true, ranking failures fall back to input order instead of raising."""
    return os.environ.get("AGENT_LOCAL_FALLBACK", "1").strip().lower() not in {
        "0",
        "false",
        "no",
    }
