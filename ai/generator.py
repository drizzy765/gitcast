import asyncio
import httpx
from ai.prompts import get_all_prompts, sprint_summary_prompt
from config.settings import (
    GROQ_API_KEY, 
    GEMINI_API_KEY, 
    DEEPSEEK_API_KEY, 
    MOONSHOT_API_KEY,
    CEREBRAS_API_KEY,
    OPENROUTER_API_KEY
)

# ── Constants ─────────────────────────────────────────────────────────────────

PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": GROQ_API_KEY,
        "model": "llama-3.3-70b-versatile",
        "tasks": ["quick_win", "struggle", "linkedin"]
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1", 
        "api_key": DEEPSEEK_API_KEY,
        "model": "deepseek-chat",
        "tasks": ["deep_tech", "pr_generator"]
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "api_key": MOONSHOT_API_KEY,
        "model": "moonshot-v1-128k",
        "tasks": ["article", "sprint_summary"]
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": CEREBRAS_API_KEY,
        "model": "llama3.3-70b",
        "tasks": []  # fallback only
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": OPENROUTER_API_KEY,
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "tasks": []  # fallback only
    }
}

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
MAX_TOKENS = 4096 
TIMEOUT = 60

# Shared client to prevent SSL/Concurrency overhead
_client = httpx.AsyncClient(timeout=TIMEOUT)


# ── Main generator ────────────────────────────────────────────────────────────

async def generate_posts(payload: dict) -> dict[str, str]:
    prompts = get_all_prompts()
    format_keys = payload.get("format_keys", list(prompts.keys()))
    user_message = payload.get("user_message", "")
    use_vision = payload.get("use_vision_fallback", False)
    
    # Handle multiple screenshots for vision
    screenshots = payload.get("screenshots", [])
    if not screenshots and payload.get("screenshot_path"):
        screenshots = [{"path": payload["screenshot_path"]}]

    selected_prompts = {k: v for k, v in prompts.items() if k in format_keys}

    output = {}
    for format_key, system_prompt in selected_prompts.items():
        print(f"[Generator] Thinking about: {format_key}...")
        try:
            if use_vision and screenshots:
                result = await _gemini_vision_call(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    screenshots=screenshots,
                )
            else:
                # Automatic task-based routing with fallback
                result = await _ai_call(format_key, system_prompt, user_message)

            output[format_key] = result
            print(f"[Generator] Variation '{format_key}' ready.")
            
            # adaptive delay
            delay = 2.0 if "article" in format_key else 1.2
            if format_key != list(selected_prompts.keys())[-1]:
                await asyncio.sleep(delay)
        except Exception as e:
            print(f"[Generator Error] Failed '{format_key}': {e}")
            output[format_key] = f"[Error] {str(e)}"

    return output


# ── Sprint generator ──────────────────────────────────────────────────────────

async def generate_sprint_summary(entries: list[dict], narrative: str = "") -> str:
    """
    Synthesizes multiple sprint captures into a single cohesive thread.
    """
    from api.payload import build_sprint_payload
    
    print(f"[Generator] Synthesizing {len(entries)} captures into a sprint thread...")
    
    payload = build_sprint_payload(entries)
    system_prompt = sprint_summary_prompt(len(entries))
    
    try:
        return await _ai_call("sprint_summary", system_prompt, payload["user_message"])
    except Exception as e:
        print(f"[Generator Error] Sprint synthesis failed: {e}")
        return f"[Error] {str(e)}"


# ── Provider Routing & Fallback ────────────────────────────────────────────────

async def _ai_call(format_key: str, system_prompt: str, user_message: str) -> str:
    """
    Identifies primary provider for a task and falls back through available providers.
    """
    # 1. Identify primary provider
    primary = "groq" # default
    for name, config in PROVIDERS.items():
        if format_key in config["tasks"]:
            primary = name
            break
            
    # 2. Build the fallback chain
    # Standard order: Primary -> Groq -> Cerebras -> DeepSeek -> Kimi -> OpenRouter -> Gemini
    chain = [primary]
    for fallback in ["groq", "cerebras", "deepseek", "kimi", "openrouter"]:
        if fallback not in chain:
            chain.append(fallback)
            
    # 3. Walk the chain
    last_error = None
    for provider_name in chain:
        try:
            return await _call_provider(provider_name, system_prompt, user_message)
        except Exception as e:
            last_error = str(e)
            print(f"[Fallback] {provider_name} failed: {e}. Trying next...")
            continue
            
    # 4. Final attempt with Gemini
    if GEMINI_API_KEY:
        print("[Fallback] All OpenAI providers failed. Trying Gemini...")
        try:
            return await _gemini_text_call(system_prompt, user_message)
        except Exception as e:
            last_error = f"Gemini also failed: {e}"

    raise Exception(f"AI chain exhausted. Last error: {last_error}")


async def _call_provider(provider_name: str, system_prompt: str, user_message: str, retries: int = 1) -> str:
    """
    Single unified function for calling any OpenAI-compatible provider.
    """
    config = PROVIDERS.get(provider_name)
    if not config or not config["api_key"]:
        raise ValueError(f"Provider {provider_name} not configured or missing API key.")

    url = f"{config['base_url'].rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    
    body = {
        "model": config["model"],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.8,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }

    for attempt in range(retries + 1):
        try:
            response = await _client.post(url, headers=headers, json=body)
            
            if response.status_code == 429:
                if attempt < retries:
                    wait = 2 + (attempt * 2)
                    await asyncio.sleep(wait)
                    continue
                raise Exception(f"Rate limit exceeded (429)")

            if response.status_code != 200:
                raise Exception(f"API Error {response.status_code}: {response.text[:100]}")

            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            print(f"[AI] Successfully used {provider_name}")
            return content

        except Exception as e:
            if attempt == retries:
                raise e
            await asyncio.sleep(1)

    raise Exception(f"Provider {provider_name} failed after retries.")


# Legacy aliases for backward compatibility with routes
async def _groq_call(system_prompt: str, user_message: str, retries: int = 2) -> str:
    # Routes might still call this directly for chat/refinement
    return await _call_provider("groq", system_prompt, user_message, retries=retries)


# ── Gemini text call ──────────────────────────────────────────────────────────

async def _gemini_text_call(system_prompt: str, user_message: str) -> str:
    """
    Fallback text generation using Gemini 1.5 Flash.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in .env")

    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}

    body = {
        "contents": [
            {
                "parts": [
                    {"text": f"System Instruction: {system_prompt}\n\nUser Message: {user_message}"}
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": MAX_TOKENS,
            "temperature": 0.7,
        },
    }

    try:
        response = await _client.post(url, headers=headers, json=body)
        if response.status_code != 200:
            print(f"[Gemini Error] {response.status_code}: {response.text}")
            response.raise_for_status()

        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"[Gemini Fallback Error] {e}")
        raise e


# ── Gemini vision call ────────────────────────────────────────────────────────

async def _gemini_vision_call(
    system_prompt: str,
    user_message: str,
    screenshots: list[dict],
) -> str:
    """
    Calls Gemini 1.5 Flash with multiple screenshots as vision inputs.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in .env")

    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}

    parts = [{"text": f"{system_prompt}\n\n{user_message}"}]
    
    # Add each screenshot
    for s in screenshots:
        b64 = _encode_image(s["path"])
        if b64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": b64,
                }
            })

    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "maxOutputTokens": MAX_TOKENS,
            "temperature": 0.85,
        },
    }

    response = await _client.post(url, headers=headers, json=body)
    if response.status_code != 200:
        raise Exception(f"Gemini Vision Error {response.status_code}: {response.text}")

    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        raise Exception("Gemini response format unexpected")


def _encode_image(image_path: str) -> str:
    import base64
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return ""


# ── Test ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    from core.capture import run_capture
    from core.ocr import run_ocr
    from api.payload import build_payload
    from config.settings import set_project_narrative

    set_project_narrative("an AI-powered build-in-public automation tool for developers")

    async def test():
        print("[Generator] Running multi-provider routing test...")
        capture = run_capture()
        ocr = run_ocr(capture["screenshot"]["path"])
        payload = build_payload(
            raw_thought="testing the new multi-provider fallback chain with Cerebras and DeepSeek",
            ocr_result=ocr,
            capture_result=capture,
        )

        payload["use_vision_fallback"] = False
        payload["screenshot_b64"] = None

        print("[Generator] Firing routed AI calls...")
        results = await generate_posts(payload)

        print("\n=== GENERATED POSTS ===")
        for format_key, content in results.items():
            print(f"\n--- {format_key.upper()} ---")
            print(content)

    asyncio.run(test())
