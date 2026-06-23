import asyncio
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from dotenv import dotenv_values, load_dotenv, set_key, unset_key
from ai.generator import generate_posts, generate_sprint_summary, _ai_call
from ai.prompts import load_prompt_definitions, PROMPTS_FILE, article_prompt, article_refinement_prompt, get_prompt
from ai.formatter import split_into_thread
from ai.viral_patterns import get_all_patterns
from api.payload import validate_payload
from api.auth_middleware import LOCAL_USER_ID, get_current_user
from storage.logger import decline_post, get_unverified_posts, load_posts, log_post, verify_post
from storage.metrics import get_metrics, save_metrics
from storage.insights import calculate_insights
from storage.tone_memory import save_rating
from storage.key_manager import encrypt_key, mask_key
from storage.supabase_client import get_client
from core.codebase_reader import summarise_for_prompt
from config.settings import (
    DEFAULTS,
    get_twitter_plan,
    load_settings,
    set_twitter_plan,
    save_settings,
    validate_api_keys,
    CURRENT_DRAFT,
    SPRINT_LOG,
    API_KEY_ENV_MAP,
    BASE_DIR,
    WAITLIST_FILE,
    reload_api_keys,
)
from core.log_stream import get_logs_after, get_latest_log_id, stream_log
from api.analytics import track
from api.ratelimit import limiter
from api.validators import (
    check_prompt_injection,
    sanitize_path,
    sanitize_text,
    validate_api_key as validate_provider_api_key,
    validate_email,
)
import json
import os

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    raw_thought: str
    ocr_text: Optional[str] = ""
    git_diff: Optional[str] = ""
    git_diff_available: Optional[bool] = False
    narrative: Optional[str] = ""
    use_vision_fallback: Optional[bool] = False
    screenshot_b64: Optional[str] = None
    screenshot_path: Optional[str] = ""
    user_message: Optional[str] = ""
    format_keys: Optional[List[str]] = None
    ocr_confidence: Optional[float] = 0.0
    working_dir: Optional[str] = ""
    timestamp: Optional[str] = ""


class PostVariation(BaseModel):
    format_key: str
    label: str
    content: str
    char_count: int
    success: bool
    error: Optional[str] = None


class GenerateResponse(BaseModel):
    success: bool
    variations: List[PostVariation]
    warnings: List[str]
    timestamp: str


class SprintRequest(BaseModel):
    entries: List[dict]
    narrative: Optional[str] = ""


class RateRequest(BaseModel):
    post_text: str
    format_key: str
    rating: int
    timestamp: Optional[str] = ""


class PromptUpdate(BaseModel):
    format_key: str
    label: str
    description: str
    system_prompt: str


class PromptDelete(BaseModel):
    format_key: str


class RecommendRequest(BaseModel):
    filename: str


class PlanUpdate(BaseModel):
    plan: str


class KeysUpdate(BaseModel):
    twitter_api_key: Optional[str] = None
    twitter_api_secret: Optional[str] = None
    twitter_access_token: Optional[str] = None
    twitter_access_secret: Optional[str] = None
    twitter_bearer_token: Optional[str] = None


class ProviderKeyUpdate(BaseModel):
    provider: str
    key: str


class ProviderKeyRemove(BaseModel):
    provider: str


class ChatRequest(BaseModel):
    message: str
    format_key: str


class CliTriggerRequest(BaseModel):
    thought: str


class CaptureTriggerRequest(BaseModel):
    delay: Optional[int] = 5


class ArticleGenerateRequest(BaseModel):
    include_codebase: Optional[bool] = False
    repo_path: Optional[str] = "."


class ArticleRefineRequest(BaseModel):
    current_article: str
    instruction: str


class ThreadSplitRequest(BaseModel):
    post_text: str


class SettingsUpdate(BaseModel):
    project_narrative: Optional[str] = None
    sprint_mode: Optional[bool] = None
    tone_memory_enabled: Optional[bool] = None
    ocr_confidence_threshold: Optional[int] = None
    screenshot_retention_hours: Optional[int] = None
    onboarding_complete: Optional[bool] = None
    preferred_providers: Optional[dict] = None
    viral_patterns_enabled: Optional[bool] = None


class PublishRequest(BaseModel):
    post_text: str
    screenshot_path: Optional[str] = None
    format_key: Optional[str] = "deep_tech"


class WaitlistRequest(BaseModel):
    email: str


class PostVerifyRequest(BaseModel):
    post_id: str
    post_url: Optional[str] = ""


class PostDeclineRequest(BaseModel):
    post_id: str


class MetricsSaveRequest(BaseModel):
    post_id: str
    impressions: int
    likes: int
    comments: int
    reposts: int
    hashtags: Optional[List[str]] = []
    days_after_post: int
    platform: Optional[str] = ""


# ── Routes ────────────────────────────────────────────────────────────────────

_INSIGHTS_CACHE = {"timestamp": 0.0, "data": None}


def invalidate_insights_cache() -> None:
    _INSIGHTS_CACHE["timestamp"] = 0.0
    _INSIGHTS_CACHE["data"] = None


# ── Local Storage Helpers (Fallback) ──────────────────────────────────────────

def load_local_posts() -> list:
    from config.settings import POST_LOG
    if not POST_LOG.exists() or POST_LOG.stat().st_size == 0:
        return []
    try:
        with open(POST_LOG, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                from storage.logger import _normalize_entry
                return [_normalize_entry(entry) for entry in data]
            return []
    except Exception:
        try:
            posts = []
            with open(POST_LOG, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        posts.append(json.loads(line))
            from storage.logger import _normalize_entry
            return [_normalize_entry(entry) for entry in posts]
        except Exception:
            return []


def save_local_posts(posts: list) -> None:
    from config.settings import POST_LOG
    try:
        POST_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(POST_LOG, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=4)
    except Exception as e:
        stream_log("Storage", "ERROR", f"Failed to save local posts: {e}")


async def safe_get_posts() -> list:
    try:
        from storage.supabase_client import get_client
        client = get_client()
        result = client.table("posts").select("*").order("timestamp", desc=True).execute()
        if result.data:
            from storage.logger import _normalize_entry
            return [_normalize_entry(entry) for entry in result.data]
        return []
    except Exception as e:
        stream_log("Storage", "WARN", f"Supabase get_posts failed: {e}. Falling back to local JSON.")
        return load_local_posts()


async def safe_save_post(post_data: dict) -> bool:
    try:
        from storage.supabase_client import get_client
        client = get_client()
        payload = {
            "post_text": post_data.get("post_text"),
            "format_key": post_data.get("format_key", "deep_tech"),
            "tweet_url": post_data.get("tweet_url", "") or post_data.get("post_url", ""),
            "tweet_id": post_data.get("tweet_id", ""),
            "provider_used": post_data.get("provider_used", ""),
            "platform": post_data.get("platform", "twitter"),
            "user_id": post_data.get("user_id"),
        }
        if "timestamp" in post_data and post_data["timestamp"]:
            payload["timestamp"] = post_data["timestamp"]
        client.table("posts").insert(payload).execute()
        return True
    except Exception as e:
        stream_log("Storage", "WARN", f"Supabase save_post failed: {e}. Falling back to local JSON.")
        posts = load_local_posts()
        from uuid import uuid4
        new_entry = {
            "id": post_data.get("id") or str(uuid4()),
            "post_text": post_data.get("post_text"),
            "format_key": post_data.get("format_key", "deep_tech"),
            "screenshot_path": post_data.get("screenshot_path", ""),
            "tweet_url": post_data.get("tweet_url", "") or post_data.get("post_url", ""),
            "tweet_id": post_data.get("tweet_id", ""),
            "fallback": post_data.get("fallback", False),
            "timestamp": post_data.get("timestamp") or datetime.now().isoformat(),
            "user_id": post_data.get("user_id", LOCAL_USER_ID),
            "posted_verified": post_data.get("posted_verified", False),
            "declined": post_data.get("declined", False) or post_data.get("posted_declined", False),
            "verified_at": post_data.get("verified_at", ""),
            "metrics_saved": post_data.get("metrics_saved", False),
            "metrics_saved_at": post_data.get("metrics_saved_at", ""),
            "impressions": post_data.get("impressions", 0),
            "likes": post_data.get("likes", 0),
            "comments": post_data.get("comments", 0),
            "reposts": post_data.get("reposts", 0),
            "hashtags": post_data.get("hashtags", []),
            "platform": post_data.get("platform", "twitter"),
            "days_after_post": post_data.get("days_after_post", 0),
        }
        posts.append(new_entry)
        save_local_posts(posts)
        return True


async def safe_update_post(post_id: str, updates: dict) -> bool:
    try:
        from storage.supabase_client import get_client
        client = get_client()
        result = client.table("posts").update(updates).eq("id", post_id).execute()
        if result.data:
            return True
        raise Exception("Post not found in Supabase")
    except Exception as e:
        stream_log("Storage", "WARN", f"Supabase update post failed: {e}. Updating local JSON.")
        posts = load_local_posts()
        found = False
        for post in posts:
            if post.get("id") == post_id:
                for k, v in updates.items():
                    if k == "declined":
                        post["declined"] = v
                        post["posted_declined"] = v
                    elif k == "posted_verified":
                        post["posted_verified"] = v
                        post["posted_declined"] = False
                        post["declined"] = False
                    else:
                        post[k] = v
                found = True
                break
        if found:
            save_local_posts(posts)
            return True
        return False


async def safe_get_unverified() -> list:
    posts = await safe_get_posts()
    unverified = [
        post for post in posts
        if not post.get("posted_verified") and not post.get("posted_declined") and not post.get("declined")
    ]
    return sorted(unverified, key=lambda item: item.get("timestamp", ""), reverse=True)


async def safe_save_metrics(post_id: str, metrics: dict) -> dict:
    payload = {
        "impressions": metrics["impressions"],
        "likes": metrics["likes"],
        "comments": metrics["comments"],
        "reposts": metrics["reposts"],
        "hashtags": metrics["hashtags"],
        "platform": metrics["platform"] or "twitter",
        "days_after_post": metrics["days_after_post"],
        "metrics_saved": True,
        "metrics_saved_at": datetime.now().isoformat(),
    }
    try:
        from storage.supabase_client import get_client
        client = get_client()
        result = client.table("posts").update(payload).eq("id", post_id).execute()
        if result.data:
            return {"success": True}
        raise Exception("Post not found in Supabase")
    except Exception as e:
        stream_log("Storage", "WARN", f"Supabase save metrics failed: {e}. Saving to local JSON.")
        posts = load_local_posts()
        found = False
        for post in posts:
            if post.get("id") == post_id:
                for k, v in payload.items():
                    post[k] = v
                found = True
                break
        if found:
            save_local_posts(posts)
            from config.settings import METRICS_LOG
            try:
                metrics_log = []
                if METRICS_LOG.exists() and METRICS_LOG.stat().st_size > 0:
                    with open(METRICS_LOG, "r", encoding="utf-8") as f:
                        metrics_log = json.load(f)
                existing = False
                for m in metrics_log:
                    if m.get("post_id") == post_id:
                        m.update(payload)
                        existing = True
                        break
                if not existing:
                    metrics_log.append({
                        "post_id": post_id,
                        **payload
                    })
                with open(METRICS_LOG, "w", encoding="utf-8") as f:
                    json.dump(metrics_log, f, indent=4)
            except Exception as e_log:
                stream_log("Storage", "ERROR", f"Failed to save metrics_log: {e_log}")
            return {"success": True}
        return {"success": False, "error": "post not found"}


KEY_GUIDE = {
    "groq": {
        "name": "Groq",
        "url": "https://console.groq.com",
        "free_tier": "12k TPM free",
        "best_for": "quick_win, struggle, linkedin",
        "required": True,
    },
    "gemini": {
        "name": "Gemini",
        "url": "https://aistudio.google.com",
        "free_tier": "1M tokens/day",
        "best_for": "vision fallback, low OCR screenshots",
        "required": False,
    },
    "kimi": {
        "name": "Kimi",
        "url": "https://platform.moonshot.ai",
        "free_tier": "free trial credits",
        "best_for": "article, sprint_summary",
        "required": False,
    },
    "cerebras": {
        "name": "Cerebras",
        "url": "https://cloud.cerebras.ai",
        "free_tier": "free inference tier",
        "best_for": "fallback generation",
        "required": False,
    },
    "openrouter": {
        "name": "OpenRouter",
        "url": "https://openrouter.ai",
        "free_tier": "free models available",
        "best_for": "final fallback via qwen/qwen3-coder:free",
        "required": False,
    },
}


def _env_path():
    path = BASE_DIR / ".env"
    path.touch(exist_ok=True)
    return path


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in API_KEY_ENV_MAP:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
    return normalized


def _is_local_user(user_id: str) -> bool:
    return user_id == LOCAL_USER_ID


def _reload_key_runtime() -> None:
    load_dotenv(_env_path(), override=True)
    reload_api_keys()
    try:
        from ai.generator import refresh_provider_keys
        refresh_provider_keys()
    except Exception as e:
        stream_log("Keys", "WARN", f"provider runtime refresh failed: {e}")


def _settings_for_user(user_id: str) -> dict:
    def local_settings() -> dict:
        settings = load_settings()
        return {**DEFAULTS, **settings, "user_id": user_id}

    if _is_local_user(user_id):
        return local_settings()

    try:
        client = get_client()
    except RuntimeError as exc:
        if "SUPABASE_URL and SUPABASE_SERVICE_KEY" not in str(exc):
            raise
        stream_log("Settings", "WARN", "Supabase not configured; using local settings")
        return local_settings()

    try:
        response = (
            client
            .table("user_settings")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        if response.data:
            return response.data[0]
        created = client.table("user_settings").insert({"user_id": user_id}).execute()
        return created.data[0] if created.data else {"user_id": user_id}
    except Exception as exc:
        stream_log("Settings", "WARN", f"Supabase settings unavailable; using local settings: {exc}")
        return local_settings()


def _update_settings_for_user(user_id: str, values: dict) -> dict:
    def save_local_settings(payload: dict) -> dict:
        settings = {**load_settings(), **payload}
        settings.pop("updated_at", None)
        save_settings(settings)
        return {**DEFAULTS, **settings, "user_id": user_id}

    payload = {key: value for key, value in values.items() if value is not None}
    if not payload:
        return _settings_for_user(user_id)
    payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    if _is_local_user(user_id):
        return save_local_settings(payload)

    try:
        client = get_client()
    except RuntimeError as exc:
        if "SUPABASE_URL and SUPABASE_SERVICE_KEY" not in str(exc):
            raise
        stream_log("Settings", "WARN", "Supabase not configured; saving local settings")
        return save_local_settings(payload)

    try:
        response = (
            client
            .table("user_settings")
            .upsert({"user_id": user_id, **payload}, on_conflict="user_id")
            .execute()
        )
        return response.data[0] if response.data else _settings_for_user(user_id)
    except Exception as exc:
        stream_log("Settings", "WARN", f"Supabase settings unavailable; saving local settings: {exc}")
        return save_local_settings(payload)


@router.get("/keys/status")
def get_ai_keys_status():
    user_id = LOCAL_USER_ID
    if _is_local_user(user_id):
        env_values = dotenv_values(_env_path())
        return {
            provider: {
                "configured": bool((env_values.get(env_name) or os.getenv(env_name) or "").strip()),
                "key_preview": "",
                "last_used_at": None,
            }
            for provider, env_name in API_KEY_ENV_MAP.items()
        }

    response = (
        get_client()
        .table("api_keys")
        .select("provider,key_preview,last_used_at,created_at")
        .eq("user_id", user_id)
        .execute()
    )
    saved = {row["provider"]: row for row in response.data or []}
    return {
        provider: {
            "configured": provider in saved,
            "key_preview": saved.get(provider, {}).get("key_preview", ""),
            "last_used_at": saved.get(provider, {}).get("last_used_at"),
        }
        for provider in API_KEY_ENV_MAP
    }


@router.post("/keys/update")
@limiter.limit("5/minute")
def update_ai_key(request: Request, body: ProviderKeyUpdate, user_id: str = Depends(get_current_user)):
    provider = _normalize_provider(sanitize_text(body.provider))
    key = (body.key or "").strip()
    if not validate_provider_api_key(key, provider):
        raise HTTPException(status_code=400, detail=f"Invalid {provider} API key format")

    try:
        if _is_local_user(user_id):
            set_key(str(_env_path()), API_KEY_ENV_MAP[provider], key)
            _reload_key_runtime()
            stream_log("Keys", "OK", f"{provider} key saved locally")
            track("api_key_added", {"provider": provider, "storage": "local"})
            return {"success": True, "provider": provider, "key_preview": mask_key(key)}

        get_client().table("api_keys").upsert(
            {
                "user_id": user_id,
                "provider": provider,
                "encrypted_key": encrypt_key(key),
                "key_preview": mask_key(key),
            },
            on_conflict="user_id,provider",
        ).execute()
        _reload_key_runtime()
        stream_log("Keys", "OK", f"{provider} key updated")
        track("api_key_added", {"provider": provider})
        return {"success": True, "provider": provider, "key_preview": mask_key(key)}
    except Exception as e:
        stream_log("Keys", "ERROR", f"{provider} key update failed: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/keys/remove")
def remove_ai_key(request: ProviderKeyRemove, user_id: str = Depends(get_current_user)):
    provider = _normalize_provider(sanitize_text(request.provider))
    try:
        if _is_local_user(user_id):
            unset_key(str(_env_path()), API_KEY_ENV_MAP[provider])
            _reload_key_runtime()
            stream_log("Keys", "OK", f"{provider} key removed locally")
            return {"success": True}

        get_client().table("api_keys").delete().eq("user_id", user_id).eq("provider", provider).execute()
        _reload_key_runtime()
        stream_log("Keys", "OK", f"{provider} key removed")
        return {"success": True}
    except Exception as e:
        stream_log("Keys", "ERROR", f"{provider} key removal failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/keys/guide")
def get_keys_guide():
    return KEY_GUIDE


@router.get("/logs/stream")
async def stream_logs():
    async def event_generator():
        last_id = max(0, get_latest_log_id() - 50)
        while True:
            entries = get_logs_after(last_id)
            for entry in entries:
                last_id = max(last_id, entry["id"])
                payload = {key: value for key, value in entry.items() if key != "id"}
                yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/waitlist")
def add_to_waitlist(request: WaitlistRequest):
    """Adds an email to the public waitlist."""
    email = sanitize_text(request.email).lower()
    if not validate_email(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    try:
        get_client().table("waitlist").upsert({"email": email, "source": "landing"}, on_conflict="email").execute()
        return {"success": True, "message": "you're on the list"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to join waitlist: {e}")


@router.patch("/settings")
@router.post("/settings")
def update_settings(update: SettingsUpdate):
    """Updates user project settings."""
    user_id = LOCAL_USER_ID
    values = update.dict(exclude_unset=True)
    if "project_narrative" in values and values["project_narrative"] is not None:
        values["project_narrative"] = sanitize_text(values["project_narrative"])
    updated = _update_settings_for_user(user_id, values)
    return {"success": True, "settings": updated}


@router.post("/publish")
@limiter.limit("10/minute")
async def publish(request: Request, body: PublishRequest):
    """Publishes a post to X (Twitter)."""
    user_id = LOCAL_USER_ID
    from publisher.twitter import publish_post
    try:
        post_text = sanitize_text(body.post_text)
        screenshot_path = sanitize_path(body.screenshot_path) if body.screenshot_path else None
        result = await asyncio.to_thread(publish_post, post_text, screenshot_path)
        if result.get("success") or result.get("fallback"):
            await safe_save_post({
                "post_text": post_text,
                "format_key": sanitize_text(body.format_key or "deep_tech"),
                "screenshot_path": body.screenshot_path or "",
                "tweet_url": result.get("tweet_url", ""),
                "tweet_id": result.get("tweet_id", ""),
                "fallback": bool(result.get("fallback")),
                "user_id": user_id,
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Publishing failed: {e}")


@router.delete("/screenshot/{filename}")
def delete_screenshot(filename: str):
    """Securely deletes a screenshot from disk."""
    from core.security import delete_capture
    from config.settings import STORAGE_DIR
    path = sanitize_path(str(STORAGE_DIR / "screenshots" / sanitize_text(filename)))
    delete_capture(str(path))
    return {"success": True}


@router.get("/screenshot/{filename}/framed")
async def get_framed_screenshot(filename: str):
    """Applies a macOS-style frame to a screenshot and returns it."""
    from PIL import Image, ImageDraw, ImageFilter
    from config.settings import STORAGE_DIR
    from fastapi.responses import Response
    import io

    path = STORAGE_DIR / "screenshots" / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")

    if filename.endswith("_framed.png"):
        from fastapi.responses import FileResponse
        return FileResponse(path, media_type="image/png", filename=filename)

    try:
        img = Image.open(path).convert("RGBA")
        
        padding = 60
        bar_height = 36
        corner_radius = 12
        
        bg_color = (26, 26, 26, 255)
        
        window_w = img.width
        window_h = img.height + bar_height
        
        bg_w = window_w + (padding * 2)
        bg_h = window_h + (padding * 2)
        bg = Image.new('RGBA', (bg_w, bg_h), bg_color)
        
        shadow_padding = 20
        shadow = Image.new('RGBA', (window_w + shadow_padding*2, window_h + shadow_padding*2), (0,0,0,0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle(
            [shadow_padding, shadow_padding, shadow_padding + window_w, shadow_padding + window_h], 
            radius=corner_radius, 
            fill=(0, 0, 0, 100)
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(15))
        
        bg.paste(shadow, (padding - shadow_padding, padding - shadow_padding), shadow)
        
        window = Image.new('RGBA', (window_w, window_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(window)
        draw.rounded_rectangle([0, 0, window_w, window_h], radius=corner_radius, fill=(255, 255, 255, 255))
        
        draw.rounded_rectangle([0, 0, window_w, bar_height], radius=corner_radius, fill=(240, 240, 240, 255))
        draw.rectangle([0, bar_height//2, window_w, bar_height], fill=(240, 240, 240, 255))

        dot_radius = 6
        dot_y = bar_height // 2
        draw.ellipse([20-dot_radius, dot_y-dot_radius, 20+dot_radius, dot_y+dot_radius], fill=(255, 95, 87, 255)) 
        draw.ellipse([42-dot_radius, dot_y-dot_radius, 42+dot_radius, dot_y+dot_radius], fill=(254, 188, 46, 255)) 
        draw.ellipse([64-dot_radius, dot_y-dot_radius, 64+dot_radius, dot_y+dot_radius], fill=(40, 200, 64, 255)) 
        
        window.paste(img, (0, bar_height), img)
        
        bg.paste(window, (padding, padding), window)
        
        img_byte_arr = io.BytesIO()
        bg.convert("RGB").save(img_byte_arr, format='PNG')
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Framing failed: {e}")


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit("10/minute")
async def generate(request: Request, body: GenerateRequest):
    user_id = LOCAL_USER_ID
    payload = body.dict()
    for key, value in list(payload.items()):
        if isinstance(value, str):
            payload[key] = sanitize_text(value)
    injection = check_prompt_injection(body.raw_thought)
    if not injection["safe"]:
        payload["raw_thought"] = injection.get("sanitized", "")
        payload["user_message"] = sanitize_text(payload.get("user_message", ""))
    
    if not payload.get("format_keys"):
        definitions = load_prompt_definitions()
        payload["format_keys"] = list(definitions.keys())

    is_valid, warnings = validate_payload(payload)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Payload has no raw thought — cannot generate posts."
        )

    try:
        results = await generate_posts(payload, user_id=user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    definitions = load_prompt_definitions()
    variations = []
    
    # Handle the helper error structure returned from generate_posts if all failed
    if "error" in results and len(results) == 1:
        error_msg = results["error"]
        for format_key in payload["format_keys"]:
            variations.append(PostVariation(
                format_key=format_key,
                label=definitions.get(format_key, {}).get("label", format_key),
                content="",
                char_count=0,
                success=False,
                error=error_msg,
            ))
    else:
        for format_key, content in results.items():
            is_error = content.startswith("[Error]")
            variations.append(PostVariation(
                format_key=format_key,
                label=definitions.get(format_key, {}).get("label", format_key),
                content=content if not is_error else "",
                char_count=len(content) if not is_error else 0,
                success=not is_error,
                error=content if is_error else None,
            ))

    return GenerateResponse(
        success=True,
        variations=variations,
        warnings=warnings,
        timestamp=payload.get("timestamp", ""),
    )


@router.get("/history")
async def get_history():
    """Returns the full history of published posts."""
    return {"history": await safe_get_posts()}


@router.get("/draft")
def get_current_draft():
    """Returns the latest captured draft from disk."""
    if not CURRENT_DRAFT.exists():
        return {"status": "empty"}
    
    try:
        with open(CURRENT_DRAFT, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading draft: {e}")


@router.post("/chat")
@limiter.limit("20/minute")
async def chat_refine(request: Request, body: ChatRequest):
    """Refines a post variation using AI chat."""
    user_id = LOCAL_USER_ID
    if not CURRENT_DRAFT.exists():
        raise HTTPException(status_code=400, detail="No active draft to refine.")

    try:
        with open(CURRENT_DRAFT, "r", encoding="utf-8") as f:
            draft = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading draft: {e}")

    message = sanitize_text(body.message)
    injection = check_prompt_injection(message)
    if not injection["safe"]:
        message = injection.get("sanitized", "")
    format_key = sanitize_text(body.format_key)
    current_text = draft["variations"].get(format_key, "")
    
    try:
        platform_prompt = get_prompt(format_key)
    except Exception as e:
        platform_prompt = f"Format/Platform key: {format_key}"

    refinement_system_prompt = (
        "You are a social media manager helping a developer refine a post.\n"
        f"The post format/platform is: '{format_key}'.\n"
        "Adhere to the platform rules and guidelines below:\n"
        "--- START PLATFORM RULES ---\n"
        f"{platform_prompt}\n"
        "--- END PLATFORM RULES ---\n\n"
        "The user will provide instructions on how to change the existing draft. "
        "Adhere strictly to the platform rules above while applying the user's changes."
    )
    
    refinement_user_message = (
        f"Original Context:\n{draft['payload']['user_message']}\n\n"
        f"Current Draft for '{format_key}':\n{current_text}\n\n"
        f"User Instruction: {message}\n\n"
        "Output ONLY the revised post text. No preamble."
    )

    try:
        new_text = await _ai_call(
            format_key,
            refinement_system_prompt,
            refinement_user_message,
            user_id=user_id,
        )
        
        draft["variations"][format_key] = new_text
        with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
            json.dump(draft, f, indent=4)
            
        return {"success": True, "new_text": new_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI refinement failed: {e}")


@router.post("/cli/trigger")
async def cli_trigger(request: CliTriggerRequest):
    """Triggers a capture workflow with a specific thought from the CLI."""
    user_id = LOCAL_USER_ID
    from core.capture import run_capture
    from core.ocr import run_ocr
    from api.payload import build_payload
    from ai.generator import generate_posts
    
    try:
        capture = await asyncio.to_thread(run_capture)
        ocr = await asyncio.to_thread(run_ocr, capture["screenshot"]["path"])
        
        payload = build_payload(
            raw_thought=sanitize_text(request.thought),
            ocr_result=ocr,
            capture_result=capture,
        )
        
        payload["use_vision_fallback"] = False
        payload["screenshot_b64"] = None
        
        variations = await generate_posts(payload, user_id=user_id)
        
        draft_data = {
            "payload": payload,
            "variations": variations,
            "timestamp": payload.get("timestamp", ""),
            "status": "ready"
        }
        with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
            json.dump(draft_data, f, indent=4)
            
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/capture/trigger")
async def ui_trigger_capture(request: CaptureTriggerRequest):
    """Triggers a capture workflow from the UI."""
    user_id = LOCAL_USER_ID
    from core.capture import run_capture
    from core.ocr import run_ocr
    from api.payload import build_payload
    from ai.generator import generate_posts
    
    stream_log("API", "INFO", f"ui_trigger_capture triggered with delay={request.delay}s")
    try:
        stream_log("API", "INFO", f"Step 1/4: Running screenshot capture (delay={request.delay}s)...")
        capture = await asyncio.to_thread(run_capture, delay=request.delay)
        screenshot_path = capture.get("screenshot", {}).get("path", "unknown")
        stream_log("API", "INFO", f"Step 1/4: Screenshot captured successfully. Path: {screenshot_path}")
        
        stream_log("API", "INFO", f"Step 2/4: Running OCR on screenshot ({screenshot_path})...")
        ocr = await asyncio.to_thread(run_ocr, screenshot_path)
        detected_text = ocr.get("text", "")
        stream_log("API", "INFO", f"Step 2/4: OCR completed. Text length: {len(detected_text)} characters.")
        
        stream_log("API", "INFO", "Step 3/4: Building payload for AI generation...")
        payload = build_payload(
            raw_thought="",
            ocr_result=ocr,
            capture_result=capture,
        )
        
        payload["use_vision_fallback"] = False
        payload["screenshot_b64"] = None
        
        stream_log("API", "INFO", "Step 4/4: Requesting AI generation from providers...")
        variations = await generate_posts(payload, user_id=user_id)
        stream_log("API", "INFO", "Step 4/4: AI generation returned.")
        
        draft_data = {
            "payload": payload,
            "variations": variations,
            "timestamp": payload.get("timestamp", ""),
            "status": "ready"
        }
        with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
            json.dump(draft_data, f, indent=4)
            
        errors = {
            key: value
            for key, value in variations.items()
            if isinstance(value, str) and value.startswith("[Error]")
        }
        return {
            "success": len(errors) < len(variations),
            "timestamp": draft_data["timestamp"],
            "errors": errors,
            "error": "AI generation failed for all formats" if errors and len(errors) == len(variations) else "",
        }
    except Exception as e:
        stream_log("API", "ERROR", f"ui_trigger_capture failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/screenshots")
def list_screenshots():
    """Lists all screenshots available in the storage directory."""
    from config.settings import STORAGE_DIR
    path = STORAGE_DIR / "screenshots"
    if not path.exists():
        return {"screenshots": []}
    
    files = []
    for f in os.listdir(path):
        if f.endswith(".png") or f.endswith(".jpg"):
            files.append({
                "filename": f,
                "path": f"storage/data/screenshots/{f}",
                "timestamp": os.path.getmtime(path / f)
            })
    
    files.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"screenshots": files}


@router.post("/screenshot/recommend")
async def recommend_screenshot(request: RecommendRequest):
    """Uses AI to recommend where to post a specific screenshot."""
    user_id = LOCAL_USER_ID
    from config.settings import STORAGE_DIR
    path = STORAGE_DIR / "screenshots" / sanitize_text(request.filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")

    system_prompt = (
        "You are a social media strategist for developers. "
        "Analyze the provided context and recommend which platform (X, LinkedIn, or a Technical Article) "
        "this screenshot is best suited for and WHY. "
        "Keep it brief: 2-3 sentences max."
    )
    
    ocr_context = "A screenshot of code or a development tool."
    if CURRENT_DRAFT.exists():
        with open(CURRENT_DRAFT, "r") as f:
            draft = json.load(f)
            for s in draft.get("payload", {}).get("screenshots", []):
                if s["path"].endswith(request.filename):
                    ocr_context = f"OCR Context: {s.get('ocr_text', 'No OCR available')}"
                    break

    try:
        recommendation = await _ai_call("deep_tech", system_prompt, f"Context: {ocr_context}", user_id=user_id)
        return {"success": True, "recommendation": recommendation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {e}")


@router.delete("/prompts/{format_key}")
def delete_prompt(format_key: str):
    """Deletes a prompt definition."""
    definitions = load_prompt_definitions()
    clean_key = sanitize_text(format_key)
    if clean_key in definitions:
        del definitions[clean_key]
        try:
            with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
                json.dump(definitions, f, indent=4)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=404, detail="Prompt not found")


@router.get("/prompts")
def get_prompts():
    """Returns all customizable prompt definitions."""
    return load_prompt_definitions()


@router.put("/prompts")
def update_prompt(update: PromptUpdate):
    """Updates a single prompt definition."""
    definitions = load_prompt_definitions()
    definitions[sanitize_text(update.format_key)] = {
        "label": sanitize_text(update.label),
        "description": sanitize_text(update.description),
        "system_prompt": sanitize_text(update.system_prompt)
    }
    
    try:
        with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
            json.dump(definitions, f, indent=4)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rate")
def rate_post(request: RateRequest):
    """Stores a rating for a historical post."""
    save_rating(
        post_text=sanitize_text(request.post_text),
        format_key=sanitize_text(request.format_key),
        rating=request.rating,
        timestamp=request.timestamp
    )
    return {"success": True}


@router.get("/formats")
def get_formats():
    """Returns available post format keys and their display labels."""
    definitions = load_prompt_definitions()
    return {"formats": {k: v["label"] for k, v in definitions.items()}}


@router.get("/settings/plan")
def get_plan():
    user_id = LOCAL_USER_ID
    settings = _settings_for_user(user_id)
    preferred = settings.get("preferred_providers") or {}
    return {"plan": preferred.get("twitter_plan", get_twitter_plan())}


@router.put("/settings/plan")
def update_plan(update: PlanUpdate):
    user_id = LOCAL_USER_ID
    plan = sanitize_text(update.plan).lower()
    settings = _settings_for_user(user_id)
    preferred = settings.get("preferred_providers") or {}
    preferred["twitter_plan"] = plan
    _update_settings_for_user(user_id, {"preferred_providers": preferred})
    return {"success": True}


@router.get("/settings")
def get_all_settings():
    user_id = LOCAL_USER_ID
    return _settings_for_user(user_id)


@router.post("/settings/sprint/toggle")
def sprint_toggle():
    user_id = LOCAL_USER_ID
    settings = _settings_for_user(user_id)
    new_state = not bool(settings.get("sprint_mode"))
    _update_settings_for_user(user_id, {"sprint_mode": new_state})
    return {"success": True, "sprint_mode": new_state}


@router.get("/settings/keys")
def get_keys_status():
    user_id = LOCAL_USER_ID
    return get_ai_keys_status()


@router.get("/diagnose")
async def diagnose_connectivity():
    """Diagnoses network and authentication status of all configured AI providers."""
    user_id = LOCAL_USER_ID
    import ai.generator
    import httpx
    
    ai.generator.refresh_provider_keys(user_id)
    
    results = {}
    
    async with httpx.AsyncClient(timeout=10) as client:
        for provider_name, config in ai.generator.PROVIDERS.items():
            if not config.get("api_key"):
                results[provider_name] = {
                    "configured": False,
                    "status": "missing_key",
                    "error": "No API key configured"
                }
                continue
            
            try:
                test_prompt = "respond with 'ok'"
                await ai.generator._call_provider(
                    provider_name=provider_name,
                    system_prompt="you are a connectivity tester",
                    user_message=test_prompt,
                    retries=0,
                    client=client
                )
                results[provider_name] = {
                    "configured": True,
                    "status": "success",
                    "error": ""
                }
            except Exception as e:
                results[provider_name] = {
                    "configured": True,
                    "status": "error",
                    "error": str(e)
                }
        
        if not ai.generator.GEMINI_API_KEY:
            results["gemini"] = {
                "configured": False,
                "status": "missing_key",
                "error": "No API key configured"
            }
        else:
            try:
                await ai.generator._gemini_text_call(
                    system_prompt="you are a connectivity tester",
                    user_message="respond with 'ok'",
                    client=client
                )
                results["gemini"] = {
                    "configured": True,
                    "status": "success",
                    "error": ""
                }
            except Exception as e:
                results["gemini"] = {
                    "configured": True,
                    "status": "error",
                    "error": str(e)
                }
                
    return {"results": results}


@router.post("/article/generate")
@limiter.limit("5/minute")
async def generate_article(request: Request, body: ArticleGenerateRequest):
    """Generates a full technical article from sprint context."""
    user_id = LOCAL_USER_ID
    if not CURRENT_DRAFT.exists():
        raise HTTPException(status_code=400, detail="No active draft to generate article from.")

    try:
        with open(CURRENT_DRAFT, "r", encoding="utf-8") as f:
            draft = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading draft: {e}")

    codebase_summary = ""
    if body.include_codebase:
        codebase_summary = await asyncio.to_thread(summarise_for_prompt, sanitize_text(body.repo_path))

    sys_prompt = article_prompt(codebase_summary)
    
    sprint_context = ""
    if SPRINT_LOG.exists():
        with open(SPRINT_LOG, "r", encoding="utf-8") as f:
            sprint_context = f.read()

    user_msg = (
        f"Raw Thoughts: {draft['payload'].get('user_message', '')}\n\n"
        f"OCR Context: {draft['payload'].get('ocr_text', '')}\n\n"
        f"Git Diff: {draft['payload'].get('git_diff', '')}\n\n"
        f"Sprint Context: {sprint_context}"
    )

    try:
        article = await _ai_call("article", sys_prompt, user_msg, user_id=user_id)
        return {"success": True, "article": article}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Article generation failed: {e}")


@router.post("/article/refine")
async def refine_article(request: ArticleRefineRequest):
    """Refines an article draft based on user instructions."""
    user_id = LOCAL_USER_ID
    current_article = sanitize_text(request.current_article)
    instruction = sanitize_text(request.instruction)
    injection = check_prompt_injection(instruction)
    if not injection["safe"]:
        instruction = injection.get("sanitized", "")
    sys_prompt = article_refinement_prompt(current_article, instruction)
    try:
        article = await _ai_call("article", sys_prompt, "Refine the article.", user_id=user_id)
        return {"success": True, "article": article}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Article refinement failed: {e}")


@router.get("/patterns")
def get_patterns():
    """Returns all available viral patterns."""
    return get_all_patterns()


@router.post("/thread/split")
def thread_split(request: ThreadSplitRequest):
    """Splits a long post into a numbered thread."""
    tweets = split_into_thread(sanitize_text(request.post_text))
    return {"success": True, "tweets": tweets}


@router.post("/posts/verify")
async def verify_logged_post(request: PostVerifyRequest):
    user_id = LOCAL_USER_ID
    post_id = sanitize_text(request.post_id)
    post_url = sanitize_text(request.post_url or "")
    result = await safe_update_post(post_id, {
        "posted_verified": True,
        "declined": False,
        "verified_at": datetime.now().isoformat(),
        "tweet_url": post_url,
    })
    if not result:
        raise HTTPException(status_code=404, detail="post not found")
    track("post_verified", {"has_url": bool(post_url)})
    return {"success": True}


@router.post("/posts/decline")
async def decline_logged_post(request: PostDeclineRequest):
    user_id = LOCAL_USER_ID
    result = await safe_update_post(sanitize_text(request.post_id), {"declined": True})
    if not result:
        raise HTTPException(status_code=404, detail="post not found")
    return {"success": True}


@router.get("/posts/unverified")
async def unverified_posts():
    return {"posts": await safe_get_unverified()}


@router.post("/metrics/save")
async def save_post_metrics(request: MetricsSaveRequest):
    user_id = LOCAL_USER_ID
    values = {
        "impressions": request.impressions,
        "likes": request.likes,
        "comments": request.comments,
        "reposts": request.reposts,
        "days_after_post": request.days_after_post,
    }
    if any(value < 0 for value in values.values()):
        raise HTTPException(status_code=400, detail="Metric values must be non-negative")
    if request.days_after_post < 1 or request.days_after_post > 30:
        raise HTTPException(status_code=400, detail="days_after_post must be between 1 and 30")

    hashtags = [sanitize_text(tag) for tag in (request.hashtags or []) if sanitize_text(tag)]
    if len(hashtags) > 10:
        raise HTTPException(status_code=400, detail="hashtags cannot exceed 10 items")

    result = await safe_save_metrics(
        sanitize_text(request.post_id),
        {
            **values,
            "hashtags": hashtags,
            "platform": sanitize_text(request.platform or ""),
        }
    )
    invalidate_insights_cache()
    track("metrics_saved", {"days_after": request.days_after_post})
    return result


@router.get("/metrics/{post_id}")
async def get_post_metrics(post_id: str):
    try:
        from storage.supabase_client import get_client
        client = get_client()
        response = (
            client.table("posts")
            .select("id,impressions,likes,comments,reposts,hashtags,platform,metrics_saved_at,days_after_post")
            .eq("id", post_id)
            .eq("metrics_saved", True)
            .execute()
        )
        if response.data:
            row = response.data[0]
            return {
                "post_id": row["id"],
                "impressions": row.get("impressions") or 0,
                "likes": row.get("likes") or 0,
                "comments": row.get("comments") or 0,
                "reposts": row.get("reposts") or 0,
                "hashtags": row.get("hashtags") or [],
                "platform": row.get("platform") or "",
                "measured_at": row.get("metrics_saved_at") or "",
                "days_after_post": row.get("days_after_post") or 0,
            }
        raise Exception("Metrics not found in Supabase")
    except Exception:
        posts = load_local_posts()
        for post in posts:
            if post.get("id") == post_id and post.get("metrics_saved"):
                return {
                    "post_id": post_id,
                    "impressions": post.get("impressions") or 0,
                    "likes": post.get("likes") or 0,
                    "comments": post.get("comments") or 0,
                    "reposts": post.get("reposts") or 0,
                    "hashtags": post.get("hashtags") or [],
                    "platform": post.get("platform") or "",
                    "measured_at": post.get("metrics_saved_at") or "",
                    "days_after_post": post.get("days_after_post") or 0,
                }
        return {}


@router.get("/insights")
async def get_insights():
    now = time.time()
    cache_key = f"data:{LOCAL_USER_ID}"
    if _INSIGHTS_CACHE.get(cache_key) is not None and now - _INSIGHTS_CACHE["timestamp"] < 3600:
        return _INSIGHTS_CACHE[cache_key]
    
    posts = await safe_get_posts()
    
    from storage.insights import _row_from_metric, _best_group, _avg
    from collections import defaultdict
    
    rows = []
    for post in posts:
        post_id = post.get("id") or post.get("timestamp")
        metrics = post.get("metrics") or {
            "impressions": post.get("impressions") or 0,
            "likes": post.get("likes") or 0,
            "comments": post.get("comments") or 0,
            "reposts": post.get("reposts") or 0,
            "hashtags": post.get("hashtags") or [],
            "platform": post.get("platform") or "",
            "measured_at": post.get("metrics_saved_at") or "",
            "days_after_post": post.get("days_after_post") or 0,
        }
        if not post.get("metrics_saved") and not post.get("metrics"):
            continue
        rows.append(_row_from_metric(post_id, metrics, post))
        
    if len(rows) < 5:
        data = {"insufficient_data": True, "posts_needed": 5 - len(rows), "posts_with_metrics": len(rows)}
    else:
        cutoff = datetime.now() - timedelta(days=30)
        recent = [row for row in rows if row["dt"] and row["dt"] >= cutoff] or rows
        
        def calculate_streak_local(posts_list: list) -> dict:
            active_posts = [p for p in posts_list if not p.get("posted_declined") and not p.get("declined")]
            if not active_posts:
                return {"current_streak": 0, "best_streak": 0, "total_posts": 0, "last_post_date": ""}
            post_dates = set()
            for entry in active_posts:
                try:
                    ts = entry.get("timestamp")
                    if ts:
                        post_dates.add(datetime.fromisoformat(str(ts).replace("Z", "+00:00")).date())
                except Exception:
                    continue
            if not post_dates:
                return {"current_streak": 0, "best_streak": 0, "total_posts": len(active_posts), "last_post_date": ""}
            sorted_dates = sorted(post_dates, reverse=True)
            last_post_date = sorted_dates[0]
            today = datetime.now().date()
            if last_post_date < today - timedelta(days=1):
                return {"current_streak": 0, "best_streak": 0, "total_posts": len(active_posts), "last_post_date": str(last_post_date)}
            
            streak_val = 1
            for i in range(1, len(sorted_dates)):
                if sorted_dates[i] == sorted_dates[i - 1] - timedelta(days=1):
                    streak_val += 1
                else:
                    break
            best_streak = 1
            running = 1
            for i in range(1, len(sorted_dates)):
                if sorted_dates[i] == sorted_dates[i - 1] - timedelta(days=1):
                    running += 1
                else:
                    best_streak = max(best_streak, running)
                    running = 1
            best_streak = max(best_streak, running)
            return {"current_streak": streak_val, "best_streak": best_streak, "total_posts": len(active_posts), "last_post_date": str(last_post_date)}
        
        streak = calculate_streak_local(posts)
        
        total_impressions = sum(row["impressions"] for row in recent)
        best_format = _best_group(rows, "format_key")
        best_day = _best_group(rows, "day")
        best_time = _best_group(rows, "time_window")
        top = max(rows, key=lambda row: row["impressions"])
        overall_avg = _avg([row["impressions"] for row in rows])
        
        patterns = []
        by_format = defaultdict(list)
        by_chars = defaultdict(list)
        by_day = defaultdict(list)
        tags = defaultdict(list)
        for row in rows:
            by_format[row["format_key"]].append(row["impressions"])
            by_chars[row["char_bucket"]].append(row["impressions"])
            by_day[row["day"]].append(row["impressions"])
            for tag in row["hashtags"]:
                tags[tag].append(row["impressions"])
                
        if len(by_format) >= 2:
            ordered = sorted(by_format.items(), key=lambda item: _avg(item[1]), reverse=True)
            high, low = ordered[0], ordered[-1]
            if _avg(low[1]) > 0:
                patterns.append({
                    "pattern": "format",
                    "description": f"{high[0].upper()} format gets {round(_avg(high[1]) / _avg(low[1]), 1)}x more impressions than {low[0].upper()}",
                    "impact": "high",
                })
        if by_chars:
            bucket, values = max(by_chars.items(), key=lambda item: _avg(item[1]))
            lift = round(((_avg(values) - overall_avg) / overall_avg) * 100, 0) if overall_avg else 0
            patterns.append({"pattern": "length", "description": f"posts in the {bucket} char bucket get {lift}% more engagement", "impact": "medium"})
        if by_day:
            day, values = max(by_day.items(), key=lambda item: _avg(item[1]))
            multiple = round(_avg(values) / overall_avg, 1) if overall_avg else 0
            patterns.append({"pattern": "day", "description": f"{day} posts get {multiple}x your average", "impact": "medium"})
            
        hashtag_performance = [
            {"hashtag": tag, "avg_impressions": round(_avg(values), 1), "uses": len(values)}
            for tag, values in sorted(tags.items(), key=lambda item: _avg(item[1]), reverse=True)
        ]
        for tag in hashtag_performance[:3]:
            patterns.append({
                "pattern": "hashtag",
                "description": f"{tag['hashtag']} adds avg {int(tag['avg_impressions'])} impressions",
                "impact": "medium",
            })
            
        data = {
            "overview": {
                "total_posts": len(recent),
                "total_verified": len([post for post in posts if post.get("posted_verified")]),
                "total_impressions": total_impressions,
                "avg_engagement_rate": round(_avg([row["engagement_rate"] for row in recent]), 2),
                "posting_streak": streak.get("current_streak", 0),
                "best_streak": streak.get("best_streak", streak.get("current_streak", 0)),
            },
            "best_format": {"format_key": best_format.get("name", ""), "avg_impressions": best_format.get("avg", 0.0), "sample_size": best_format.get("sample_size", 0)},
            "best_day": {"day": best_day.get("name", ""), "avg_impressions": best_day.get("avg", 0.0)},
            "best_time": {"window": best_time.get("name", ""), "avg_impressions": best_time.get("avg", 0.0)},
            "top_post": {key: top[key] for key in ["post_text", "impressions", "likes", "format_key", "timestamp"]},
            "viral_patterns": patterns[:8],
            "hashtag_performance": hashtag_performance[:20],
        }
        
    _INSIGHTS_CACHE["timestamp"] = now
    _INSIGHTS_CACHE[cache_key] = data
    return data
