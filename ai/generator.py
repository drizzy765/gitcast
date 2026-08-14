import os
import asyncio
import httpx
import uuid
from datetime import datetime
from ai.prompts import get_all_prompts, sprint_summary_prompt
from core.log_stream import stream_log
from api.analytics import track
from config.settings import (
    GROQ_API_KEY,
    GEMINI_API_KEY,
    MOONSHOT_API_KEY,
    CEREBRAS_API_KEY,
    OPENROUTER_API_KEY,
    DEEPSEEK_API_KEY,
    GROQ_MODEL,
    MOONSHOT_MODEL,
    GEMINI_MODEL,
    CEREBRAS_MODEL,
    OPENROUTER_MODEL,
)

# ── Constants ─────────────────────────────────────────────────────────────────

PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": GROQ_API_KEY,
        "model": GROQ_MODEL,
        "tasks": ["quick_win", "struggle", "linkedin", "deep_tech", "pr_generator", "x_post"]
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "api_key": CEREBRAS_API_KEY,
        "model": CEREBRAS_MODEL,
        "tasks": []  # fallback only
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": GEMINI_API_KEY,
        "model": GEMINI_MODEL,
        "tasks": []  # fallback only
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": OPENROUTER_API_KEY,
        "model": OPENROUTER_MODEL,
        "tasks": []  # fallback only
    },
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",
        "api_key": MOONSHOT_API_KEY,
        "model": MOONSHOT_MODEL,
        "tasks": ["article", "sprint_summary"]
    },
    "deepseek": {
        "base_url": os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1"),
        "api_key": DEEPSEEK_API_KEY,
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "tasks": ["pr_desc"]
    }
}

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
MAX_TOKENS = 4096 
TIMEOUT = 15

_last_call_meta = {"provider_used": "", "used_fallback": False}


class ProviderUnavailable(Exception):
    def __init__(self, provider: str, message: str, status_code: int | None = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _load_user_provider_keys(user_id: str) -> dict:
    return {}


def refresh_provider_keys(user_id: str = "") -> None:
    from config import settings

    settings.reload_api_keys()
    user_keys = _load_user_provider_keys(user_id) if user_id else {}
    PROVIDERS["groq"]["api_key"] = settings.GROQ_API_KEY
    PROVIDERS["groq"]["model"] = settings.GROQ_MODEL
    PROVIDERS["cerebras"]["api_key"] = settings.CEREBRAS_API_KEY
    PROVIDERS["cerebras"]["model"] = settings.CEREBRAS_MODEL
    PROVIDERS["gemini"]["api_key"] = settings.GEMINI_API_KEY
    PROVIDERS["gemini"]["model"] = settings.GEMINI_MODEL
    PROVIDERS["openrouter"]["api_key"] = settings.OPENROUTER_API_KEY
    PROVIDERS["openrouter"]["model"] = settings.OPENROUTER_MODEL
    PROVIDERS["kimi"]["api_key"] = settings.MOONSHOT_API_KEY
    PROVIDERS["kimi"]["model"] = settings.MOONSHOT_MODEL
    PROVIDERS["deepseek"]["api_key"] = settings.DEEPSEEK_API_KEY
    PROVIDERS["deepseek"]["model"] = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    global GEMINI_API_KEY
    global GEMINI_URL
    GEMINI_API_KEY = settings.GEMINI_API_KEY
    GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
    for provider, api_key in user_keys.items():
        if provider == "gemini":
            GEMINI_API_KEY = api_key
            PROVIDERS["gemini"]["api_key"] = api_key
        elif provider in PROVIDERS:
            PROVIDERS[provider]["api_key"] = api_key


# ── Main generator ────────────────────────────────────────────────────────────

async def generate_posts(payload: dict, user_id: str = "") -> dict:
    async def _generate_all():
        refresh_provider_keys(user_id)
        prompts = get_all_prompts()
        format_keys = payload.get("format_keys", list(prompts.keys()))
        user_message = payload.get("user_message", "")
        use_vision = payload.get("use_vision_fallback", False)
        
        screenshots = payload.get("screenshots", [])
        if not screenshots and payload.get("screenshot_path"):
            screenshots = [{"path": payload["screenshot_path"]}]

        selected_prompts = {k: v for k, v in prompts.items() if k in format_keys}

        output = {}
        unavailable = {}

        async def run_one(format_key, system_prompt, client):
            started = asyncio.get_event_loop().time()
            active_user_message = user_message
            if format_key == "pr_generator":
                if "## Screen context" in active_user_message:
                    parts = active_user_message.split("## Screen context")
                    prefix = parts[0].strip()
                    suffix = parts[1].strip()
                    if "## " in suffix:
                        next_idx = suffix.find("## ")
                        active_user_message = prefix + "\n\n" + suffix[next_idx:].strip()
                    else:
                        active_user_message = prefix
            
            local_meta = {"provider_used": "", "used_fallback": False}
            try:
                if use_vision and screenshots and format_key != "pr_generator":
                    stream_log("ROUTER", "ROUTER", f"{format_key} -> gemini vision fallback")
                    stream_log("GENERATOR", "INFO", f"generating {format_key} via gemini...")
                    t0 = asyncio.get_event_loop().time()
                    try:
                        result = await _gemini_vision_call(
                            system_prompt=system_prompt,
                            user_message=active_user_message,
                            screenshots=screenshots,
                            client=client,
                        )
                        elapsed = asyncio.get_event_loop().time() - t0
                        stream_log("GENERATOR", "OK", f"{format_key} complete ({elapsed:.1f}s)")
                        local_meta.update({"provider_used": "gemini", "used_fallback": True})
                    except Exception as e:
                        print(f"[Generator] {format_key} failed on gemini: {e}")
                        stream_log("GENERATOR", "WARN", f"{format_key} failed on gemini — trying fallback")
                        raise e
                else:
                    result = await _ai_call(
                        format_key,
                        system_prompt,
                        active_user_message,
                        user_id=user_id,
                        unavailable=unavailable,
                        client=client,
                        meta=local_meta,
                    )

                output[format_key] = result
                elapsed = asyncio.get_event_loop().time() - started
                track("post_generated", {
                    "format_keys": [format_key],
                    "provider_used": local_meta.get("provider_used", ""),
                    "latency_seconds": round(elapsed, 1),
                    "used_fallback": bool(local_meta.get("used_fallback", False)),
                })
            except Exception as e:
                stream_log("Generator", "ERROR", f"{format_key} failed: {e}")
                output[format_key] = f"[Error] {str(e)}"

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            tasks = [
                run_one(format_key, system_prompt, client)
                for format_key, system_prompt in selected_prompts.items()
            ]
            await asyncio.gather(*tasks)
            
        # Check if all format generation failed
        all_failed = True
        for format_key in format_keys:
            val = output.get(format_key)
            if val and not val.startswith("[Error]"):
                all_failed = False
                break
                
        if all_failed:
            return {"error": "all providers failed — check your API keys"}
            
        return output

    try:
        # Add a 30 second total timeout across all calls
        return await asyncio.wait_for(_generate_all(), timeout=30.0)
    except asyncio.TimeoutError:
        stream_log("Generator", "ERROR", "Generation timed out after 30 seconds")
        return {"error": "all providers failed — check your API keys"}
    except Exception as e:
        stream_log("Generator", "ERROR", f"Generation failed: {e}")
        return {"error": "all providers failed — check your API keys"}


# ── Sprint generator ──────────────────────────────────────────────────────────

async def generate_sprint_summary(entries: list, narrative: str = "", user_id: str = "") -> str:
    """
    Synthesizes multiple sprint captures into a single cohesive thread.
    """
    from api.payload import build_sprint_payload
    
    stream_log("Generator", "AI", f"synthesizing {len(entries)} captures into sprint thread")
    
    refresh_provider_keys(user_id)
    payload = build_sprint_payload(entries)
    system_prompt = sprint_summary_prompt(len(entries))
    
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            return await _ai_call("sprint_summary", system_prompt, payload["user_message"], user_id=user_id, client=client)
    except Exception as e:
        stream_log("Generator", "ERROR", f"sprint synthesis failed: {e}")
        return f"[Error] {str(e)}"


# ── Provider Routing & Fallback ────────────────────────────────────────────────

async def _ai_call(
    format_key: str,
    system_prompt: str,
    user_message: str,
    user_id: str = "",
    unavailable: dict[str, str] | None = None,
    client: httpx.AsyncClient = None,
    meta: dict | None = None,
) -> str:
    """
    Identifies primary provider for a task and falls back through available providers.
    """
    unavailable = unavailable if unavailable is not None else {}

    # 1. Identify primary provider
    primary = "groq" # default
    for name, config in PROVIDERS.items():
        if format_key in config["tasks"]:
            primary = name
            break
            
    # 2. Build the fallback chain
    # Preferred order: Primary -> Groq -> Cerebras -> Gemini -> OpenRouter -> Kimi -> DeepSeek
    chain = [primary]
    for fallback in ["groq", "cerebras", "gemini", "openrouter", "kimi", "deepseek"]:
        if fallback not in chain:
            chain.append(fallback)
            
    # 3. Walk the chain
    last_error = None
    stream_log("ROUTER", "ROUTER", f"{format_key} -> {primary}")
    
    async def run_chain(active_client: httpx.AsyncClient):
        nonlocal last_error
        for provider_name in chain:
            if provider_name in unavailable:
                stream_log("ROUTER", "WARN", f"{provider_name} skipped: {unavailable[provider_name]}")
                last_error = unavailable[provider_name]
                continue
            
            stream_log("GENERATOR", "INFO", f"generating {format_key} via {provider_name}...")
            t0 = asyncio.get_event_loop().time()
            try:
                if provider_name != primary:
                    stream_log("ROUTER", "ROUTER", f"{format_key} -> {provider_name} fallback")
                result = await _call_provider(provider_name, system_prompt, user_message, client=active_client)
                _last_call_meta.update({
                    "provider_used": provider_name,
                    "used_fallback": provider_name != primary,
                })
                if meta is not None:
                    meta.update({
                        "provider_used": provider_name,
                        "used_fallback": provider_name != primary,
                    })
                elapsed = asyncio.get_event_loop().time() - t0
                stream_log("GENERATOR", "OK", f"{format_key} complete ({elapsed:.1f}s)")
                return result
            except ProviderUnavailable as e:
                last_error = str(e)
                unavailable[e.provider] = str(e)
                print(f"[Generator] {format_key} failed on {provider_name}: {e}")
                stream_log("GENERATOR", "WARN", f"{format_key} failed on {provider_name} — trying fallback")
                continue
            except Exception as e:
                last_error = str(e)
                unavailable[provider_name] = str(e)
                print(f"[Generator] {format_key} failed on {provider_name}: {e}")
                stream_log("GENERATOR", "WARN", f"{format_key} failed on {provider_name} — trying fallback")
                continue

        raise Exception(f"AI chain exhausted. Last error: {last_error}")

    if client:
        return await run_chain(client)
    else:
        async with httpx.AsyncClient(timeout=TIMEOUT) as local_client:
            return await run_chain(local_client)


async def _call_provider(
    provider_name: str,
    system_prompt: str,
    user_message: str,
    retries: int = 1,
    client: httpx.AsyncClient = None,
) -> str:
    """
    Single unified function for calling any provider (OpenAI-compatible or Gemini).
    """
    if provider_name == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("Provider gemini not configured or missing API key.")
        return await _gemini_text_call(system_prompt, user_message, client=client)

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

    is_local_client = client is None
    active_client = client if client is not None else httpx.AsyncClient(timeout=TIMEOUT)
    try:
        for attempt in range(retries + 1):
            try:
                stream_log(provider_name, "AI", f"Calling {config['model']} (timeout={TIMEOUT}s, attempt {attempt + 1}/{retries + 1})")
                response = await active_client.post(url, headers=headers, json=body, timeout=TIMEOUT)
                
                if response.status_code == 429:
                    if attempt < retries:
                        wait = 2 + (attempt * 2)
                        stream_log(provider_name, "WARN", f"Rate limited (429). Retrying in {wait}s...")
                        await asyncio.sleep(wait)
                        continue
                    raise ProviderUnavailable(provider_name, "Rate limit exceeded (429)", 429)

                if response.status_code in {402, 404}:
                    raise ProviderUnavailable(
                        provider_name,
                        f"API Error {response.status_code}: {response.text[:180]}",
                        response.status_code,
                    )

                if response.status_code != 200:
                    raise Exception(f"API Error {response.status_code}: {response.text[:180]}")

                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()
                stream_log(provider_name, "OK", "Provider call complete successfully.")
                return content

            except httpx.TimeoutException as te:
                stream_log(provider_name, "ERROR", f"Request to {provider_name} timed out after {TIMEOUT}s: {te}")
                if attempt == retries:
                    raise ProviderUnavailable(provider_name, f"Request to {provider_name} timed out after {TIMEOUT}s", 408)
                await asyncio.sleep(1)
            except Exception as e:
                stream_log(provider_name, "ERROR", f"Request to {provider_name} failed: {e}")
                if attempt == retries:
                    raise e
                await asyncio.sleep(1)
    finally:
        if is_local_client:
            await active_client.aclose()

    raise Exception(f"Provider {provider_name} failed after retries.")


# Legacy aliases for backward compatibility with routes
async def _groq_call(system_prompt: str, user_message: str, retries: int = 2) -> str:
    return await _call_provider("groq", system_prompt, user_message, retries=retries)


# ── Gemini text call ──────────────────────────────────────────────────────────

async def _gemini_text_call(system_prompt: str, user_message: str, client: httpx.AsyncClient = None) -> str:
    """
    Fallback text generation using Gemini 1.5 Flash.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in .env")

    url = GEMINI_URL
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }

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

    is_local_client = client is None
    active_client = client if client is not None else httpx.AsyncClient(timeout=TIMEOUT)
    try:
        stream_log("Gemini", "AI", f"Calling Gemini text fallback API (timeout={TIMEOUT}s)")
        response = await active_client.post(url, headers=headers, json=body, timeout=TIMEOUT)
        if response.status_code != 200:
            detail = response.text[:240]
            stream_log("Gemini", "ERROR", f"Text call failed with {response.status_code}: {detail}")
            if response.status_code in {400, 401, 403, 404, 429}:
                raise ProviderUnavailable("gemini", f"Gemini API Error {response.status_code}: {detail}", response.status_code)
            raise Exception(f"Gemini API Error {response.status_code}: {detail}")

        data = response.json()
        stream_log("Gemini", "OK", "Gemini text fallback complete successfully.")
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except httpx.TimeoutException as te:
        stream_log("Gemini", "ERROR", f"Gemini text fallback call timed out after {TIMEOUT}s: {te}")
        raise te
    except Exception as e:
        stream_log("Gemini", "ERROR", f"Gemini text fallback failed: {e}")
        raise e
    finally:
        if is_local_client:
            await active_client.aclose()


# ── Gemini vision call ────────────────────────────────────────────────────────

async def _gemini_vision_call(
    system_prompt: str,
    user_message: str,
    screenshots: list,
    client: httpx.AsyncClient = None,
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

    is_local_client = client is None
    active_client = client if client is not None else httpx.AsyncClient(timeout=TIMEOUT)
    try:
        stream_log("Gemini", "AI", f"Calling Gemini vision with {len(parts) - 1} screenshot(s) (timeout={TIMEOUT}s)")
        response = await active_client.post(url, headers=headers, json=body, timeout=TIMEOUT)
        if response.status_code != 200:
            raise Exception(f"Gemini Vision Error {response.status_code}: {response.text}")

        data = response.json()
        stream_log("Gemini", "OK", "Gemini vision call complete successfully.")
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except httpx.TimeoutException as te:
        stream_log("Gemini", "ERROR", f"Gemini vision call timed out after {TIMEOUT}s: {te}")
        raise te
    except (KeyError, IndexError):
        raise Exception("Gemini response format unexpected")
    except Exception as e:
        stream_log("Gemini", "ERROR", f"Gemini vision call failed: {e}")
        raise e
    finally:
        if is_local_client:
            await active_client.aclose()


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
            raw_thought="testing the new multi-provider fallback chain with Cerebras and OpenRouter",
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
