import asyncio
import json
import os
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel

from schema import ResponseFormat

from utils.serper_client import search_web

DEFAULT_REASONING_EFFORT = "low"
DEFAULT_MAX_WEB_SEARCH_LOOPS = 8


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

    async def _execute_tool_calls(self, tool_calls, messages: list[dict]):
        """Execute python functions requested by LLM and append results to messages."""
        if not tool_calls:
            return False
            
        tool_results_added = False
        for tool_call in tool_calls:
            function_name = getattr(tool_call.function, "name", "")
            arguments_str = getattr(tool_call.function, "arguments", "{}")
            tool_call_id = getattr(tool_call, "id", "")
            
            try:
                kwargs = json.loads(arguments_str)
            except json.JSONDecodeError:
                kwargs = {}
                
            if function_name == "search_web":
                query = kwargs.get("query", "")
                print(f"[Tool Call] Executing search_web for: {query}")
                result = await search_web(query)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result
                })
                tool_results_added = True
            else:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": f"Error: Tool '{function_name}' is not supported by this client."
                })
                tool_results_added = True
                
        return tool_results_added

    def _build_serper_tool_schema(self) -> dict[str, Any]:
        """Return the JSON schema tool definition for search_web."""
        return {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the internet using Serper API to find recent information, technical details, or factual evidence.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query string."
                        }
                    },
                    "required": ["query"],
                    "additionalProperties": False
                }
            }
        }

    @staticmethod
    def _extract_message_text(message: Any) -> str:
        """Extract plain text content from an SDK message object."""
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return ""

        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    parts.append(item["text"])
                continue

            item_type = getattr(item, "type", None)
            if item_type == "text":
                text_value = getattr(item, "text", None)
                if isinstance(text_value, str):
                    parts.append(text_value)
                    continue
                nested_value = getattr(text_value, "value", None)
                if isinstance(nested_value, str):
                    parts.append(nested_value)

        return "".join(parts)

    @classmethod
    def _coerce_structured_response(
        cls,
        response_format: type[BaseModel],
        message: Any,
    ) -> Optional[BaseModel]:
        """Best-effort conversion when SDK parsed output is missing."""
        parsed = getattr(message, "parsed", None)
        if parsed is not None:
            return parsed

        raw_text = cls._extract_message_text(message).strip()
        if not raw_text:
            return None

        model_fields = getattr(response_format, "model_fields", {})
        if set(model_fields) == {"content"}:
            return response_format(content=raw_text)

        try:
            return response_format.model_validate_json(raw_text)
        except Exception:
            pass

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return None

        try:
            return response_format.model_validate(payload)
        except Exception:
            return None

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
        
        # We handle tool calls internally now if use_web_search is True
        if use_web_search:
            merged_tools = []
            if tools:
                merged_tools.extend(tools)
            merged_tools.append(self._build_serper_tool_schema())
            request_kwargs["tools"] = merged_tools
            if not tool_choice:
                request_kwargs["tool_choice"] = "auto"
        elif tools:
            request_kwargs["tools"] = tools
            if tool_choice:
                request_kwargs["tool_choice"] = tool_choice

        current_messages = list(messages)
        max_tool_loops = DEFAULT_MAX_WEB_SEARCH_LOOPS
        
        for i in range(max_tool_loops):
            kwargs_for_this_loop = dict(request_kwargs)
            # On the final loop, force the model to answer by removing tools
            if i == max_tool_loops - 1 and "tools" in kwargs_for_this_loop:
                print("Warning: Max tool loops reached. Forcing final answer by disabling tools.")
                kwargs_for_this_loop.pop("tools")
                kwargs_for_this_loop.pop("tool_choice", None)

            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=current_messages,
                **kwargs_for_this_loop,
            )
            
            message = response.choices[0].message
            current_messages.append(message.model_dump(exclude_none=True))
            
            if message.tool_calls:
                # Execute tools and append results
                await self._execute_tool_calls(message.tool_calls, current_messages)
                # Loop continues, sending the results back to the LLM
            else:
                return message.content or ""
                
        return "Error: Maximum tool execution loops reached without final answer."

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

        # We handle tool calls internally now if use_web_search is True
        if use_web_search:
            merged_tools = []
            if tools:
                merged_tools.extend(tools)
            merged_tools.append(self._build_serper_tool_schema())
            request_kwargs["tools"] = merged_tools
            if not tool_choice:
                request_kwargs["tool_choice"] = "auto"
        elif tools:
            request_kwargs["tools"] = tools
            if tool_choice:
                request_kwargs["tool_choice"] = tool_choice

        current_messages = list(messages)
        max_tool_loops = DEFAULT_MAX_WEB_SEARCH_LOOPS
        empty_retries = 0
        max_empty_retries = 2

        for i in range(max_tool_loops):
            kwargs_for_this_loop = dict(request_kwargs)
            # On the final loop, force the model to answer by removing tools
            if i == max_tool_loops - 1 and "tools" in kwargs_for_this_loop:
                print("Warning: Max tool loops reached in structured call. Forcing parsed output by disabling tools.")
                kwargs_for_this_loop.pop("tools")
                kwargs_for_this_loop.pop("tool_choice", None)

            # Beta parse API
            response = await self.client.beta.chat.completions.parse(
                model=self.model_name,
                messages=current_messages,
                response_format=response_format,
                **kwargs_for_this_loop,
            )

            message = response.choices[0].message

            # Check for model refusal
            refusal = getattr(message, "refusal", None)
            if refusal:
                print(f"Warning: Model refused the request: {refusal}")

            # Ensure tool_calls is not None before checking or iterating
            tool_calls = getattr(message, "tool_calls", None)

            if tool_calls:
                # Keep the raw assistant message for tool call context
                current_messages.append(message.model_dump(exclude_none=True, exclude={"parsed"}))
                # Execute tools and append results
                await self._execute_tool_calls(tool_calls, current_messages)
            else:
                structured_response = self._coerce_structured_response(response_format, message)
                if structured_response is not None:
                    return structured_response

                # Empty response: retry instead of immediately crashing
                # Do NOT append the empty assistant message — Gemini rejects empty parts
                raw_text = self._extract_message_text(message).strip()
                empty_retries += 1
                if empty_retries <= max_empty_retries:
                    preview = raw_text[:300] if raw_text else "<empty>"
                    print(
                        f"Warning: Empty/unparseable structured response (attempt {empty_retries}/{max_empty_retries}), "
                        f"retrying... Preview: {preview}"
                    )
                    continue

                preview = raw_text[:300] if raw_text else "<empty>"
                raise ValueError(
                    "Structured response parsing failed after retries: model returned no parseable content "
                    f"for {response_format.__name__}. Preview: {preview}"
                )

        return None

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

        if use_web_search:
            merged_tools = []
            if tools:
                merged_tools.extend(tools)
            merged_tools.append(self._build_serper_tool_schema())
            request_kwargs["tools"] = merged_tools
            if not tool_choice:
                request_kwargs["tool_choice"] = "auto"
        elif tools:
            request_kwargs["tools"] = tools
            if tool_choice:
                request_kwargs["tool_choice"] = tool_choice

        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True,
            **request_kwargs,
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
