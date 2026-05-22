from __future__ import annotations

import json
import os
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # Keep the demo runnable without optional LLM dependency.
    OpenAI = None  # type: ignore[assignment]


def _load_local_env(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value


class LLMError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(self) -> None:
        _load_local_env()
        self.disabled = os.environ.get("LLM_DISABLED", "").lower() in ("1", "true", "yes")
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")
        self.base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.api_key = os.environ.get("LLM_API_KEY") or deepseek_key
        self.model = os.environ.get("LLM_MODEL", "deepseek-v4-pro")
        self.reasoning_effort = os.environ.get("LLM_REASONING_EFFORT", "high")
        self.thinking_type = os.environ.get("LLM_THINKING", "enabled")
        self.client = None
        if OpenAI is not None and self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    @property
    def enabled(self) -> bool:
        return bool(not self.disabled and self.client and self.model)

    def chat_json(self, system_prompt: str, user_prompt: str, timeout: int = 40) -> dict[str, Any]:
        if not self.enabled:
            raise LLMError("LLM is not configured. Install openai and set DEEPSEEK_API_KEY or LLM_API_KEY.")
        timeout = int(os.environ.get("LLM_TIMEOUT", timeout))

        last_error: Exception | None = None
        prompts = [
            user_prompt,
            f"{user_prompt}\n\nReturn one non-empty JSON object only. Do not return markdown or prose.",
        ]

        for prompt in prompts:
            try:
                response = self.client.chat.completions.create(  # type: ignore[union-attr]
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    stream=False,
                    timeout=timeout,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    reasoning_effort=self.reasoning_effort,
                    extra_body={"thinking": {"type": self.thinking_type}},
                )
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("empty message content")
                return self._parse_json_content(content)
            except Exception as exc:
                last_error = exc

        raise LLMError(f"LLM response is not valid JSON after retry: {last_error}") from last_error

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start < 0 or end <= start:
                raise
            data = json.loads(content[start : end + 1])
        if not isinstance(data, dict):
            raise ValueError("top-level JSON is not an object")
        return data
