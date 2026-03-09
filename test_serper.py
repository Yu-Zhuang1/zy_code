import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path so we can import utils.serper_client
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.serper_client import search_web, _load_env

async def check_serper():
    print("=== Testing Serper API Integration ===")
    
    # Check 1: Loading Environment Variables
    _load_env()
    api_key = os.getenv("SERPER_API_KEY")
    
    if not api_key:
        print("❌ Error: SERPER_API_KEY not found in environment!")
        print("   -> Please make sure your .env file exists in the project root and contains SERPER_API_KEY=your_key")
        return
        
    print(f"✅ SERPER_API_KEY detected (starts with: {api_key[:8]}...)")
    
    # Check 2: Running a real search query
    query = "AI Agent framework galaxy"
    print(f"🔍 Executing search query: '{query}'")
    
    try:
        # We test the client function directly
        result = await search_web(query, num_results=3)
        
        if result.startswith("Error:") or result.startswith("Web search failed:"):
            print("❌ Search Failed!")
            print(f"Error Details: {result}")
        else:
            print("✅ Search Successful! Results received:")
            print("-" * 50)
            print(result)
            print("-" * 50)
            
    except Exception as e:
        print(f"❌ Unexpected script error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(check_serper())
