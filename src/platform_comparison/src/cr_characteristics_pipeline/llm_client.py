"""OpenAI-compatible chat completion client used by the annotation pipeline."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Protocol

from src.cr_characteristics_pipeline import config


class ChatClient(Protocol):
    def complete_json(self, messages: list[dict[str, str]]) -> str:
        """Return the model response content as a JSON string."""


class OpenAICompatibleClient:
    """Minimal stdlib client for OpenAI-compatible /chat/completions APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        load_dotenv()
        self.api_key = api_key or os.environ.get(config.LLM_API_KEY_ENV)
        self.base_url = (
            base_url
            or os.environ.get(config.LLM_API_BASE_URL_ENV)
            or config.LLM_DEFAULT_API_BASE_URL
        ).rstrip("/")
        self.model = model or os.environ.get(config.LLM_MODEL_ENV) or config.LLM_DEFAULT_MODEL

    def complete_json(self, messages: list[dict[str, str]]) -> str:
        if not self.api_key:
            raise RuntimeError(
                f"Missing LLM API key. Set environment variable {config.LLM_API_KEY_ENV}."
            )

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": config.LLM_TEMPERATURE,
            "max_tokens": config.LLM_MAX_TOKENS,
            "response_format": config.LLM_RESPONSE_FORMAT,
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + config.LLM_CHAT_COMPLETIONS_PATH,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        last_error: Exception | None = None
        for attempt in range(config.LLM_RETRY_COUNT):
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=config.LLM_TIMEOUT_SECONDS,
                ) as response:
                    response_payload = json.loads(response.read().decode("utf-8"))
                return _extract_content(response_payload)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"LLM HTTP {exc.code}: {detail}")
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc

            if attempt < config.LLM_RETRY_COUNT - 1:
                time.sleep(config.LLM_RETRY_BACKOFF_SECONDS * (attempt + 1))

        raise RuntimeError(f"LLM request failed after retries: {last_error}")


class MockLLMClient:
    """Deterministic no-network client for smoke tests and CLI dry-runs."""

    def complete_json(self, messages: list[dict[str, str]]) -> str:
        labels = {
            key: {
                config.LABEL_PRESENT_FIELD: False,
                config.LABEL_EVIDENCE_FIELD: "",
            }
            for key in config.CHARACTERISTIC_KEYS
        }
        return json.dumps({"labels": labels, "notes": "mock response"})


def _extract_content(response_payload: dict[str, Any]) -> str:
    try:
        return response_payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected LLM response shape: {response_payload}") from exc


def load_dotenv() -> None:
    """Load key=value pairs from the repo-level .env file if it exists."""
    env_path = config.ENV_FILE_PATH
    if not env_path.exists():
        return

    with open(env_path, encoding=config.ENV_FILE_ENCODING) as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = _strip_env_value(value.strip())
            if not key:
                continue
            if config.ENV_FILE_OVERRIDE_EXISTING:
                os.environ[key] = value
            else:
                os.environ.setdefault(key, value)


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
