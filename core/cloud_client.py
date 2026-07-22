import os

import httpx

from config.settings import GITCAST_API_URL, BYOK_KEY, BYOK_PROVIDER

TIMEOUT = 60
SERVER_SLEEPING_MSG = (
    "Server is waking up (first request after "
    "inactivity takes ~30 seconds). Please wait..."
)


def _byok_key() -> str:
    return os.getenv("BYOK_KEY", BYOK_KEY)


def _byok_provider() -> str:
    return os.getenv("BYOK_PROVIDER", BYOK_PROVIDER)


def get_headers() -> dict:
    """
    Build request headers.
    If user has BYOK key, send it as a header
    so the server uses it instead of base key.
    """
    headers = {"Content-Type": "application/json"}
    key = _byok_key()
    if key:
        headers["X-BYOK-Key"] = key
        headers["X-BYOK-Provider"] = _byok_provider()
    return headers


async def cloud_generate(payload: dict) -> dict:
    """
    Send payload to cloud server for AI generation.
    Returns dict of format_key -> generated post.
    """
    import asyncio

    url = f"{GITCAST_API_URL}/api/generate"
    headers = get_headers()
    body = dict(payload)
    key = _byok_key()

    if key:
        body["byok_key"] = key
        body["byok_provider"] = _byok_provider()

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            print("[Cloud] Sending to Gitcast server...")
            res = await client.post(url, headers=headers, json=body)

            if res.status_code == 503:
                print(f"[Cloud] {SERVER_SLEEPING_MSG}")
                await asyncio.sleep(5)
                res = await client.post(url, headers=headers, json=body)

            res.raise_for_status()
            data = res.json()

            variations = data.get("variations", {})
            if isinstance(variations, list):
                variations = {
                    item.get("format_key"): item.get("content", "")
                    for item in variations
                    if item.get("format_key")
                }
            if isinstance(variations, dict):
                nudge = variations.pop("_rate_limit_nudge", None)
                if nudge:
                    print(f"\n[Gitcast] {nudge}\n")
                    print(
                        "[Gitcast] Run: "
                        "gitcast --setup to add "
                        "your own free key"
                    )
                return variations
            return {}

    except httpx.TimeoutException:
        print("[Cloud] Request timed out - server may be waking up, try again")
        return {}
    except httpx.ConnectError:
        print("[Cloud] Cannot reach Gitcast server - check your internet connection")
        return {}
    except Exception as e:
        print(f"[Cloud] Error: {e}")
        return {}


async def cloud_refine(
    current_post: str,
    instruction: str,
    format_key: str,
) -> str:
    """Send refinement request to cloud server."""
    url = f"{GITCAST_API_URL}/api/chat"
    headers = get_headers()
    payload = {
        "current_post": current_post,
        "instruction": instruction,
        "format_key": format_key,
    }
    key = _byok_key()
    if key:
        payload["byok_key"] = key
        payload["byok_provider"] = _byok_provider()

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            res = await client.post(url, headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            return data.get("refined_post", "")
    except Exception as e:
        print(f"[Cloud] Refine error: {e}")
        return current_post


async def cloud_save_post(post_data: dict) -> dict:
    """Save post to cloud storage via server."""
    url = f"{GITCAST_API_URL}/api/posts/save"
    headers = get_headers()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(url, headers=headers, json=post_data)
            res.raise_for_status()
            return res.json()
    except Exception as e:
        print(f"[Cloud] Save post error: {e}")
        return post_data


async def cloud_get_posts(session_id: str) -> list:
    """Get posts from cloud storage."""
    url = f"{GITCAST_API_URL}/api/posts/{session_id}"
    headers = get_headers()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()
            return data.get("posts", [])
    except Exception as e:
        print(f"[Cloud] Get posts error: {e}")
        return []


def check_server_health() -> dict:
    """
    Check if cloud server is reachable and
    all providers are configured.
    Returns health dict.
    """
    try:
        res = httpx.get(f"{GITCAST_API_URL}/health", timeout=10)
        return res.json()
    except Exception:
        return {"status": "unreachable"}
