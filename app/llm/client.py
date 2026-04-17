"""Provider-agnostic async LLM client for Groq, Gemini, and Anthropic."""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator

import httpx


class LLMClientError(Exception):
    """Raised for LLM provider API failures."""


class LLMClient:
    """Model-agnostic LLM client. Supports Groq, Gemini, and Anthropic."""

    def __init__(self, provider: str, api_key: str, model: str):
        self.provider = provider.strip().lower()
        self.api_key = api_key
        self.model = model

        if self.provider not in {"groq", "gemini", "anthropic"}:
            raise ValueError("provider must be one of: groq | gemini | anthropic")

    async def complete(
        self,
        messages: list[dict],
        system: str | None = None,
        json_mode: bool = False,
    ) -> str:
        """Non-streaming completion. Used for planning step."""
        if self.provider == "groq":
            return await self._groq_complete(messages, system=system, json_mode=json_mode)
        if self.provider == "gemini":
            return await self._gemini_complete(messages, system=system, json_mode=json_mode)
        return await self._anthropic_complete(messages, system=system, json_mode=json_mode)

    async def stream(
        self,
        messages: list[dict],
        system: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming completion. Used for final response synthesis."""
        if self.provider == "groq":
            async for token in self._groq_stream(messages, system=system):
                yield token
            return
        if self.provider == "anthropic":
            async for token in self._anthropic_stream(messages, system=system):
                yield token
            return

        # Gemini streaming endpoint compatibility can vary. Fallback to split tokens.
        full = await self._gemini_complete(messages, system=system, json_mode=False)
        for part in full.split(" "):
            yield part + " "

    async def _groq_complete(self, messages: list[dict], system: str | None, json_mode: bool) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload_messages = self._to_openai_messages(messages, system)
        payload: dict[str, Any] = {
            "model": self.model or "llama-3.3-70b-versatile",
            "messages": payload_messages,
            "temperature": 0.1,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            raise LLMClientError(f"Groq error {response.status_code}: {response.text[:300]}")

        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def _groq_stream(self, messages: list[dict], system: str | None) -> AsyncGenerator[str, None]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": self.model or "llama-3.3-70b-versatile",
            "messages": self._to_openai_messages(messages, system),
            "temperature": 0.2,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise LLMClientError(f"Groq stream error {response.status_code}: {body.decode('utf-8', 'ignore')[:300]}")
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line.removeprefix("data:").strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    async def _gemini_complete(self, messages: list[dict], system: str | None, json_mode: bool) -> str:
        model = self.model or "gemini-2.0-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        parts = self._to_gemini_parts(messages)

        payload: dict[str, Any] = {
            "contents": parts,
            "generationConfig": {"temperature": 0.2},
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            payload["generationConfig"].update(
                {
                    "responseMimeType": "application/json",
                    "responseSchema": {
                        "type": "OBJECT",
                    },
                }
            )

        params = {"key": self.api_key}
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, params=params, json=payload)
        if response.status_code >= 400:
            raise LLMClientError(f"Gemini error {response.status_code}: {response.text[:300]}")

        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        blocks = candidates[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in blocks)

    async def _anthropic_complete(self, messages: list[dict], system: str | None, json_mode: bool) -> str:
        payload_messages = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages]
        sys_prompt = system or ""
        if json_mode:
            sys_prompt = (
                f"{sys_prompt}\nReturn JSON only enclosed in <json>...</json> tags."
            ).strip()

        payload = {
            "model": self.model or "claude-sonnet-4-20250514",
            "max_tokens": 2048,
            "messages": payload_messages,
            "system": sys_prompt,
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        if response.status_code >= 400:
            raise LLMClientError(f"Anthropic error {response.status_code}: {response.text[:300]}")

        data = response.json()
        text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        if json_mode:
            start = text.find("<json>")
            end = text.rfind("</json>")
            if start != -1 and end != -1 and end > start:
                return text[start + len("<json>"):end].strip()
        return text

    async def _anthropic_stream(self, messages: list[dict], system: str | None) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model or "claude-sonnet-4-20250514",
            "max_tokens": 2048,
            "messages": [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in messages],
            "system": system or "",
            "stream": True,
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", "https://api.anthropic.com/v1/messages", headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise LLMClientError(f"Anthropic stream error {response.status_code}: {body.decode('utf-8', 'ignore')[:300]}")

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data_str = line.removeprefix("data:").strip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "content_block_delta":
                        text = event.get("delta", {}).get("text")
                        if text:
                            yield text

    @staticmethod
    def _to_openai_messages(messages: list[dict], system: str | None) -> list[dict[str, str]]:
        payload: list[dict[str, str]] = []
        if system:
            payload.append({"role": "system", "content": system})
        for msg in messages:
            payload.append(
                {
                    "role": str(msg.get("role", "user")),
                    "content": str(msg.get("content", "")),
                }
            )
        return payload

    @staticmethod
    def _to_gemini_parts(messages: list[dict]) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for msg in messages:
            role = "user" if msg.get("role") != "assistant" else "model"
            output.append({"role": role, "parts": [{"text": str(msg.get("content", ""))}]})
        return output
