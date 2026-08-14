import asyncio
import httpx
import os
import sys
from pathlib import Path

# Add project root to path so we can import config
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import (
    GROQ_API_KEY, GEMINI_API_KEY,
    MOONSHOT_API_KEY, CEREBRAS_API_KEY, OPENROUTER_API_KEY
)

async def check_provider(name, url, headers, body, is_gemini=False):
    print(f"Testing {name.upper()}...", end=" ", flush=True)
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            if is_gemini:
                res = await client.post(f"{url}?key={GEMINI_API_KEY}", json=body)
            else:
                res = await client.post(url, headers=headers, json=body)
            
            if res.status_code == 200:
                print("✅ WORKING")
                return True
            else:
                print(f"❌ FAILED ({res.status_code})")
                try:
                    error_msg = res.json().get('error', {}).get('message', res.text[:100])
                    print(f"   Reason: {error_msg}")
                except:
                    print(f"   Reason: {res.text[:100]}")
                return False
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            return False

async def main():
    print("=== Context Engine API Key Connectivity Test ===\n")
    
    # 1. Groq
    await check_provider(
        "Groq", 
        "https://api.groq.com/openai/v1/chat/completions",
        {"Authorization": f"Bearer {GROQ_API_KEY}"},
        {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
    )

    # 2. OpenRouter
    await check_provider(
        "OpenRouter",
        "https://openrouter.ai/api/v1/chat/completions",
        {"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        {"model": "openrouter/free", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
    )

    # 3. Kimi (Moonshot)
    await check_provider(
        "Moonshot (Kimi)", 
        "https://api.moonshot.cn/v1/chat/completions",
        {"Authorization": f"Bearer {MOONSHOT_API_KEY}"},
        {"model": "moonshot-v1-8k", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
    )

    # 4. Cerebras
    await check_provider(
        "Cerebras", 
        "https://api.cerebras.ai/v1/chat/completions",
        {"Authorization": f"Bearer {CEREBRAS_API_KEY}"},
        {"model": "gpt-oss-120b", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
    )

    # 5. Gemini
    await check_provider(
        "Gemini", 
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
        {},
        {"contents": [{"parts": [{"text": "hi"}]}]},
        is_gemini=True
    )

    print("\nTest complete.")

def test_api_keys_script():
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
