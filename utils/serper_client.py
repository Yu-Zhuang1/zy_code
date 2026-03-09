import os
import httpx
from dotenv import load_dotenv

def _load_env():
    # Only load it if the key isn't already in the environment
    if not os.getenv("SERPER_API_KEY"):
        # We rely on llm_client.py's load_env_config having run,
        # but just in case, try loading the generic one
        try:
            from llm_client import load_env_config
            load_env_config()
        except ImportError:
            pass

async def search_web(query: str, num_results: int = 5) -> str:
    """
    Search the web using the Serper API.
    
    Args:
        query: The search query string.
        num_results: The maximum number of organic results to return.
        
    Returns:
        A concise string containing the top search results.
    """
    _load_env()
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        return "Error: SERPER_API_KEY environment variable is missing. Cannot perform web search."
    
    url = "https://google.serper.dev/search"
    payload = {
        "q": query,
        "num": num_results
    }
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            organic_results = data.get("organic", [])
            if not organic_results:
                return "No organic results found for the query."
            
            # Format the output for the LLM
            formatted_results = []
            for i, result in enumerate(organic_results[:num_results], 1):
                title = result.get("title", "No Title")
                snippet = result.get("snippet", "No Snippet")
                link = result.get("link", "No Link")
                formatted_results.append(f"[{i}] {title}\nSummary: {snippet}\nSource: {link}\n")
                
            return "\n".join(formatted_results)
            
    except httpx.HTTPStatusError as e:
        return f"Web search failed: HTTP error {e.response.status_code}"
    except httpx.RequestError as e:
        return f"Web search failed: Request error {str(e)}"
    except Exception as e:
        return f"Web search failed: Unexpected error {str(e)}"
