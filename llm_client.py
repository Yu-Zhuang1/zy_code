import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel
from schema import ResponseFormat


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


class LLMClient:
    """LLM Client using OpenRouter API."""
    
    def __init__(self, model_name: str):
        """
        Initialize the LLM client.
        
        Args:
            model_name: The name of the model to use (e.g., "openai/gpt-4", "anthropic/claude-3-opus")
        """
        # Load environment variables
        load_env_config()
        
        # Get configuration from environment
        self.base_url = os.getenv("OPENROUTER_BASE_URL")
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model_name = model_name
        # === 调试代码 START ===
        print(f"DEBUG: Base URL is: '{self.base_url}'") 
        # 注意不要打印完整的 Key，只打印前几位验证是否读取到了
        print(f"DEBUG: API Key starts with: '{self.api_key[:10] if self.api_key else 'None'}...'")
        # === 调试代码 END ===
        
        # Validate configuration
        if not self.base_url:
            raise ValueError("OPENROUTER_BASE_URL not found in .env file")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in .env file")
        
        # Initialize OpenAI client with OpenRouter configuration
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    async def close(self):
        """Close the underlying client session."""
        await self.client.close()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def chat(self, messages: list[dict], **kwargs) -> str:
        """
        Send a chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            **kwargs: Additional parameters to pass to the API
        
        Returns:
            The assistant's response content
        """
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content
    
    async def chat_structured(self, messages: list[dict], response_format: BaseModel = ResponseFormat, **kwargs) -> BaseModel:
        """
        Send a chat completion request and return structured output matching the response_format.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            response_format: The Pydantic model to enforce structure (defaults to ResponseFormat)
            **kwargs: Additional parameters to pass to the API
        
        Returns:
            The parsed object instance of response_format
        """
        response = await self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=messages,
            response_format=response_format,
            **kwargs
        )
        return response.choices[0].message.parsed

    async def chat_stream(self, messages: list[dict], **kwargs):
        """
        Send a streaming chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            **kwargs: Additional parameters to pass to the API
        
        Yields:
            Content chunks from the streaming response
        """
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True,
            **kwargs
        )
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# Example usage
if __name__ == "__main__":
    async def main():
        # Example: Create a client with a specific model using async context manager
        async with LLMClient(model_name="openai/gpt-5.2") as client:
            
            # Example chat
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "为我编造10个人的名字和年龄"}
            ]
            
            print("Running normal chat...")
            response = await client.chat(messages)
            print("Normal Response:", response)
            
            # Example structured output
            print("\nRequesting structured output...")
            structured_response = await client.chat_structured(messages)
            print("Structured Response:", structured_response.results)
            print("Items:")
            if structured_response.results:
                for item in structured_response.results:
                    print(f"- Name: {item.name}, Age: {item.age}")

    asyncio.run(main())
