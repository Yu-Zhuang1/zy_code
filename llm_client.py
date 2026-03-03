import asyncio
import os
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

from schema import ResponseFormat

DEFAULT_REASONING_EFFORT = "low"


def get_project_root() -> Path:
    """Get the project root directory (where .env file is located)."""
    return Path(__file__).parent


def load_env_config():
    """Load environment variables from .env file in project root."""
    project_root = get_project_root()
    env_path = project_root / ".env"

    if not env_path.exists():
        raise FileNotFoundError(f".env file not found at {env_path}")

    load_dotenv(env_path)


def _get_env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"Invalid {name}={raw!r}, fallback to default: {default}")
        return default


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"Invalid {name}={raw!r}, fallback to default: {default}")
        return default


class LLMClient:
    """LLM Client using OpenRouter API."""

    def __init__(self, model_name: str, reasoning_effort: Optional[str] = None):
        """
        Initialize the LLM client.

        Args:
            model_name: The model name, e.g. "openai/gpt-5.2"
            reasoning_effort: Default reasoning effort for calls unless caller overrides it
        """
        load_env_config()

        self.base_url = os.getenv("OPENROUTER_BASE_URL")
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model_name = model_name
        cleaned_effort = (reasoning_effort or "").strip()
        self.default_reasoning_effort = cleaned_effort or DEFAULT_REASONING_EFFORT
        self.timeout_seconds = max(1.0, _get_env_float("LLM_TIMEOUT_SECONDS", 10800.0))
        self.client_max_retries = max(0, _get_env_int("LLM_CLIENT_MAX_RETRIES", 2))
        self.web_search_tool_types = self._load_web_search_tool_types()

        if not self.base_url:
            raise ValueError("OPENROUTER_BASE_URL not found in .env file")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in .env file")

        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=httpx.Timeout(self.timeout_seconds),
            max_retries=self.client_max_retries,
        )

    @staticmethod
    def _load_web_search_tool_types() -> list[str]:
        """
        Load preferred web search tool types from env.
        Defaults to a compatibility order that works across common gateways.
        """
        raw_value = os.getenv("WEB_SEARCH_TOOL_TYPE", "web_search,web_search_preview")
        candidates = [item.strip() for item in raw_value.split(",") if item.strip()]
        if not candidates:
            candidates = ["web_search", "web_search_preview"]

        ordered: list[str] = []
        seen = set()
        for item in candidates:
            if item in seen:
                continue
            seen.add(item)
            ordered.append(item)
        return ordered

    @staticmethod
    def _merge_tools(
        tools: Optional[list[dict[str, Any]]] = None,
        web_search_tool_type: Optional[str] = None,
    ) -> Optional[list[dict[str, Any]]]:
        merged_tools: list[dict[str, Any]] = []
        if tools:
            merged_tools.extend(tools)

        if web_search_tool_type:
            has_same_type = any(
                isinstance(tool, dict) and tool.get("type") == web_search_tool_type
                for tool in merged_tools
            )
            if not has_same_type:
                merged_tools.append({"type": web_search_tool_type})
        return merged_tools or None

    def _with_default_reasoning(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        request_kwargs = dict(kwargs)
        request_kwargs.setdefault("reasoning_effort", self.default_reasoning_effort)
        return request_kwargs

    async def close(self):
        """Close the underlying client session."""
        await self.client.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def chat(self, messages: list[dict], use_web_search: bool = False, **kwargs) -> str:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            use_web_search: Whether to enable built-in web search tool
            **kwargs: Additional parameters to pass to the API

        Returns:
            The assistant response content
        """
        tools = kwargs.pop("tools", None)
        tool_choice = kwargs.pop("tool_choice", None)
        request_kwargs = self._with_default_reasoning(kwargs)

        response = None
        last_error = None
        if use_web_search:
            for tool_type in self.web_search_tool_types:
                try:
                    request_kwargs_with_search = dict(request_kwargs)
                    merged_tools = self._merge_tools(tools, web_search_tool_type=tool_type)
                    if merged_tools:
                        request_kwargs_with_search["tools"] = merged_tools
                        request_kwargs_with_search["tool_choice"] = tool_choice or "auto"

                    response = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        **request_kwargs_with_search,
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    print(f"Warning: web search tool '{tool_type}' failed ({exc}). Trying fallback.")

        if response is None:
            if use_web_search and last_error:
                print("Warning: web search unavailable, retrying without search tool.")

            request_kwargs_no_search = dict(request_kwargs)
            merged_tools = self._merge_tools(tools)
            if merged_tools:
                request_kwargs_no_search["tools"] = merged_tools
                request_kwargs_no_search["tool_choice"] = tool_choice or "auto"

            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **request_kwargs_no_search,
            )

        return response.choices[0].message.content

    async def chat_structured(
        self,
        messages: list[dict],
        response_format: type[BaseModel] = ResponseFormat,
        use_web_search: bool = False,
        **kwargs,
    ) -> BaseModel:
        """
        Send a structured chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            response_format: Pydantic model type for structured output
            use_web_search: Whether to enable built-in web search tool
            **kwargs: Additional parameters to pass to the API

        Returns:
            Parsed object instance of response_format
        """
        tools = kwargs.pop("tools", None)
        tool_choice = kwargs.pop("tool_choice", None)
        request_kwargs = self._with_default_reasoning(kwargs)

        response = None
        last_error = None
        if use_web_search:
            for tool_type in self.web_search_tool_types:
                try:
                    request_kwargs_with_search = dict(request_kwargs)
                    merged_tools = self._merge_tools(tools, web_search_tool_type=tool_type)
                    if merged_tools:
                        request_kwargs_with_search["tools"] = merged_tools
                        request_kwargs_with_search["tool_choice"] = tool_choice or "auto"

                    response = await self.client.beta.chat.completions.parse(
                        model=self.model_name,
                        messages=messages,
                        response_format=response_format,
                        **request_kwargs_with_search,
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    print(
                        f"Warning: structured call with web search '{tool_type}' failed ({exc}). Trying fallback."
                    )

        if response is None:
            if use_web_search and last_error:
                print("Warning: structured call fallback to request without web search.")

            request_kwargs_no_search = dict(request_kwargs)
            merged_tools = self._merge_tools(tools)
            if merged_tools:
                request_kwargs_no_search["tools"] = merged_tools
                request_kwargs_no_search["tool_choice"] = tool_choice or "auto"

            response = await self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=messages,
                response_format=response_format,
                **request_kwargs_no_search,
            )

        return response.choices[0].message.parsed

    async def chat_stream(self, messages: list[dict], use_web_search: bool = False, **kwargs):
        """
        Send a streaming chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            use_web_search: Whether to enable built-in web search tool
            **kwargs: Additional parameters to pass to the API
        """
        tools = kwargs.pop("tools", None)
        tool_choice = kwargs.pop("tool_choice", None)
        request_kwargs = self._with_default_reasoning(kwargs)

        response = None
        last_error = None
        if use_web_search:
            for tool_type in self.web_search_tool_types:
                try:
                    request_kwargs_with_search = dict(request_kwargs)
                    merged_tools = self._merge_tools(tools, web_search_tool_type=tool_type)
                    if merged_tools:
                        request_kwargs_with_search["tools"] = merged_tools
                        request_kwargs_with_search["tool_choice"] = tool_choice or "auto"
                    response = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        stream=True,
                        **request_kwargs_with_search,
                    )
                    break
                except Exception as exc:
                    last_error = exc
                    print(f"Warning: stream with web search '{tool_type}' failed ({exc}). Trying fallback.")

        if response is None:
            if use_web_search and last_error:
                print("Warning: stream fallback to request without web search.")
            request_kwargs_no_search = dict(request_kwargs)
            merged_tools = self._merge_tools(tools)
            if merged_tools:
                request_kwargs_no_search["tools"] = merged_tools
                request_kwargs_no_search["tool_choice"] = tool_choice or "auto"
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=True,
                **request_kwargs_no_search,
            )

        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


if __name__ == "__main__":
    async def main():
        async with LLMClient(model_name="openai/gpt-5.2") as client:
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "为我编造10个人的名字和年龄"},
            ]

            print("Running normal chat...")
            response = await client.chat(messages)
            print("Normal Response:", response)

            print("\nRequesting structured output...")
            structured_response = await client.chat_structured(messages)
            print("Structured Response:", structured_response.results)
            print("Items:")
            if structured_response.results:
                for item in structured_response.results:
                    print(f"- Name: {item.name}, Age: {item.age}")

    asyncio.run(main())
