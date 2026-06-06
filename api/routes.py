import asyncio
import time
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from dotenv import dotenv_values, load_dotenv, set_key, unset_key
from ai.generator import generate_posts, generate_sprint_summary, _ai_call
from ai.prompts import load_prompt_definitions, PROMPTS_FILE, article_prompt, article_refinement_prompt
from ai.formatter import split_into_thread
from ai.viral_patterns import get_all_patterns
from api.payload import validate_payload
from api.auth_middleware import get_current_user
from storage.logger import decline_post, get_unverified_posts, load_posts, log_post, verify_post
from storage.metrics import get_metrics, save_metrics
from storage.insights import calculate_insights
from storage.tone_memory import save_rating
from storage.key_manager import encrypt_key, mask_key
from storage.supabase_client import get_client
from core.codebase_reader import summarise_for_prompt
from config.settings import (
    get_twitter_plan,
    set_twitter_plan,
    validate_api_keys,
    CURRENT_DRAFT,
    SPRINT_LOG,
    AI_ROUTING_MAP,
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

KEY_GUIDE = {
    "groq": {
        "name": "Groq",
        "url": "https://console.groq.com",
        "free_tier": "12k TPM free",
        "best_for": "quick_win, struggle, linkedin",
        "required": True,
    },
    "deepseek": {
        "name": "DeepSeek",
        "url": "https://platform.deepseek.com",
        "free_tier": "$5 credit on signup",
        "best_for": "deep_tech, pr_generator",
        "required": False,
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
        "best_for": "fallback generation",
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


def _reload_key_runtime() -> None:
    load_dotenv(_env_path(), override=True)
    reload_api_keys()
    try:
        from ai.generator import refresh_provider_keys
        refresh_provider_keys()
    except Exception as e:
        stream_log("Keys", "WARN", f"provider runtime refresh failed: {e}")


def _settings_for_user(user_id: str) -> dict:
    response = (
        get_client()
        .table("user_settings")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    if response.data:
        return response.data[0]
    created = get_client().table("user_settings").insert({"user_id": user_id}).execute()
    return created.data[0] if created.data else {"user_id": user_id}


def _update_settings_for_user(user_id: str, values: dict) -> dict:
    payload = {key: value for key, value in values.items() if value is not None}
    if not payload:
        return _settings_for_user(user_id)
    payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    response = (
        get_client()
        .table("user_settings")
        .upsert({"user_id": user_id, **payload}, on_conflict="user_id")
        .execute()
    )
    return response.data[0] if response.data else _settings_for_user(user_id)


@router.get("/keys/status")
def get_ai_keys_status(user_id: str = Depends(get_current_user)):
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
        get_client().table("api_keys").delete().eq("user_id", user_id).eq("provider", provider).execute()
        _reload_key_runtime()
        stream_log("Keys", "OK", f"{provider} key removed")
        return {"success": True}
    except Exception as e:
        stream_log("Keys", "ERROR", f"{provider} key removal failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/keys/guide")
def get_keys_guide(user_id: str = Depends(get_current_user)):
    return KEY_GUIDE


@router.get("/logs/stream")
async def stream_logs(user_id: str = Depends(get_current_user)):
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


@router.post("/settings")
def update_settings(update: SettingsUpdate, user_id: str = Depends(get_current_user)):
    """Updates user project settings."""
    values = update.dict(exclude_unset=True)
    if "project_narrative" in values and values["project_narrative"] is not None:
        values["project_narrative"] = sanitize_text(values["project_narrative"])
    updated = _update_settings_for_user(user_id, values)
    return {"success": True, "settings": updated}


@router.post("/publish")
@limiter.limit("10/minute")
async def publish(request: Request, body: PublishRequest, user_id: str = Depends(get_current_user)):
    """Publishes a post to X (Twitter)."""
    from publisher.twitter import publish_post
    try:
        post_text = sanitize_text(body.post_text)
        screenshot_path = sanitize_path(body.screenshot_path) if body.screenshot_path else None
        result = publish_post(post_text, screenshot_path)
        if result.get("success") or result.get("fallback"):
            log_post(
                post_text=post_text,
                format_key=sanitize_text(body.format_key or "deep_tech"),
                screenshot_path=body.screenshot_path or "",
                tweet_url=result.get("tweet_url", ""),
                tweet_id=result.get("tweet_id", ""),
                fallback=bool(result.get("fallback")),
                user_id=user_id,
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Publishing failed: {e}")


@router.delete("/screenshot/{filename}")
def delete_screenshot(filename: str, user_id: str = Depends(get_current_user)):
    """Securely deletes a screenshot from disk."""
    from core.security import delete_capture
    from config.settings import STORAGE_DIR
    path = sanitize_path(str(STORAGE_DIR / "screenshots" / sanitize_text(filename)))
    delete_capture(str(path))
    return {"success": True}


@router.get("/screenshot/{filename}/framed")
async def get_framed_screenshot(filename: str, user_id: str = Depends(get_current_user)):
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
        
        # Outer bg color #1a1a1a
        bg_color = (26, 26, 26, 255)
        
        # Window canvas
        window_w = img.width
        window_h = img.height + bar_height
        
        # New background
        bg_w = window_w + (padding * 2)
        bg_h = window_h + (padding * 2)
        bg = Image.new('RGBA', (bg_w, bg_h), bg_color)
        
        # Create shadow
        shadow_padding = 20
        shadow = Image.new('RGBA', (window_w + shadow_padding*2, window_h + shadow_padding*2), (0,0,0,0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle(
            [shadow_padding, shadow_padding, shadow_padding + window_w, shadow_padding + window_h], 
            radius=corner_radius, 
            fill=(0, 0, 0, 100)
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(15))
        
        # Paste shadow
        bg.paste(shadow, (padding - shadow_padding, padding - shadow_padding), shadow)
        
        # Create window with rounded corners
        window = Image.new('RGBA', (window_w, window_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(window)
        draw.rounded_rectangle([0, 0, window_w, window_h], radius=corner_radius, fill=(255, 255, 255, 255))
        
        # Title bar background (light gray)
        draw.rounded_rectangle([0, 0, window_w, bar_height], radius=corner_radius, fill=(240, 240, 240, 255))
        # Fill the bottom of the title bar to square the corners that meet the content
        draw.rectangle([0, bar_height//2, window_w, bar_height], fill=(240, 240, 240, 255))

        # Draw dots
        dot_radius = 6
        dot_y = bar_height // 2
        draw.ellipse([20-dot_radius, dot_y-dot_radius, 20+dot_radius, dot_y+dot_radius], fill=(255, 95, 87, 255)) # Red
        draw.ellipse([42-dot_radius, dot_y-dot_radius, 42+dot_radius, dot_y+dot_radius], fill=(254, 188, 46, 255)) # Yellow
        draw.ellipse([64-dot_radius, dot_y-dot_radius, 64+dot_radius, dot_y+dot_radius], fill=(40, 200, 64, 255)) # Green
        
        # Paste screenshot content
        window.paste(img, (0, bar_height), img)
        
        # Final paste window on bg
        bg.paste(window, (padding, padding), window)
        
        img_byte_arr = io.BytesIO()
        bg.convert("RGB").save(img_byte_arr, format='PNG')
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Framing failed: {e}")


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit("10/minute")
async def generate(request: Request, body: GenerateRequest, user_id: str = Depends(get_current_user)):
    payload = body.dict()
    for key, value in list(payload.items()):
        if isinstance(value, str):
            payload[key] = sanitize_text(value)
    injection = check_prompt_injection(body.raw_thought)
    if not injection["safe"]:
        payload["raw_thought"] = injection.get("sanitized", "")
        payload["user_message"] = sanitize_text(payload.get("user_message", ""))
    
    # Use all prompts if no specific format keys provided
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
def get_history(user_id: str = Depends(get_current_user)):
    """Returns the full history of published posts."""
    return {"history": load_posts(user_id)}


@router.get("/draft")
def get_current_draft(user_id: str = Depends(get_current_user)):
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
async def chat_refine(request: Request, body: ChatRequest, user_id: str = Depends(get_current_user)):
    """Refines a post variation using AI chat."""
    if not CURRENT_DRAFT.exists():
        raise HTTPException(status_code=400, detail="No active draft to refine.")

    try:
        with open(CURRENT_DRAFT, "r", encoding="utf-8") as f:
            draft = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading draft: {e}")

    # Build the refinement prompt
    message = sanitize_text(body.message)
    injection = check_prompt_injection(message)
    if not injection["safe"]:
        message = injection.get("sanitized", "")
    format_key = sanitize_text(body.format_key)
    current_text = draft["variations"].get(format_key, "")
    
    # Simple refinement instruction
    refinement_system_prompt = (
        "You are a social media manager helping a developer refine a post. "
        "The user will provide instructions on how to change an existing draft. "
        "Keep the same general format rules but apply the user's changes strictly."
    )
    
    refinement_user_message = (
        f"Original Context:\n{draft['payload']['user_message']}\n\n"
        f"Current Draft for '{format_key}':\n{current_text}\n\n"
        f"User Instruction: {message}\n\n"
        "Output ONLY the revised post text. No preamble."
    )

    try:
        # Use routing for the specific format_key
        new_text = await _ai_call(
            format_key,
            refinement_system_prompt,
            refinement_user_message,
            user_id=user_id,
        )
        
        # Update and save
        draft["variations"][format_key] = new_text
        with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
            json.dump(draft, f, indent=4)
            
        return {"success": True, "new_text": new_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI refinement failed: {e}")


@router.post("/cli/trigger")
async def cli_trigger(request: CliTriggerRequest, user_id: str = Depends(get_current_user)):
    """Triggers a capture workflow with a specific thought from the CLI."""
    from core.capture import run_capture
    from core.ocr import run_ocr
    from api.payload import build_payload
    from ai.generator import generate_posts
    
    try:
        capture = run_capture()
        ocr = run_ocr(capture["screenshot"]["path"])
        
        payload = build_payload(
            raw_thought=sanitize_text(request.thought),
            ocr_result=ocr,
            capture_result=capture,
        )
        
        # force Groq
        payload["use_vision_fallback"] = False
        payload["screenshot_b64"] = None
        
        variations = await generate_posts(payload, user_id=user_id)
        
        # Save to CURRENT_DRAFT
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
async def ui_trigger_capture(request: CaptureTriggerRequest, user_id: str = Depends(get_current_user)):
    """Triggers a capture workflow from the UI."""
    from core.capture import run_capture
    from core.ocr import run_ocr
    from api.payload import build_payload
    from ai.generator import generate_posts
    
    try:
        # Use provided delay (0 if UI handled countdown)
        capture = run_capture(delay=request.delay)
        ocr = run_ocr(capture["screenshot"]["path"])
        
        payload = build_payload(
            raw_thought="",
            ocr_result=ocr,
            capture_result=capture,
        )
        
        # force Groq
        payload["use_vision_fallback"] = False
        payload["screenshot_b64"] = None
        
        variations = await generate_posts(payload, user_id=user_id)
        
        # Save to CURRENT_DRAFT
        draft_data = {
            "payload": payload,
            "variations": variations,
            "timestamp": payload.get("timestamp", ""),
            "status": "ready"
        }
        with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
            json.dump(draft_data, f, indent=4)
            
        return {"success": True, "timestamp": draft_data["timestamp"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/screenshots")
def list_screenshots(user_id: str = Depends(get_current_user)):
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
    
    # Sort by newest first
    files.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"screenshots": files}


@router.post("/screenshot/recommend")
async def recommend_screenshot(request: RecommendRequest, user_id: str = Depends(get_current_user)):
    """Uses AI to recommend where to post a specific screenshot."""
    from config.settings import STORAGE_DIR
    path = STORAGE_DIR / "screenshots" / sanitize_text(request.filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")

    # Simple approach: use the filename or associated OCR if we can find it
    system_prompt = (
        "You are a social media strategist for developers. "
        "Analyze the provided context and recommend which platform (X, LinkedIn, or a Technical Article) "
        "this screenshot is best suited for and WHY. "
        "Keep it brief: 2-3 sentences max."
    )
    
    # Try to find associated OCR from current draft if it matches
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
def delete_prompt(format_key: str, user_id: str = Depends(get_current_user)):
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
def get_prompts(user_id: str = Depends(get_current_user)):
    """Returns all customizable prompt definitions."""
    return load_prompt_definitions()


@router.put("/prompts")
def update_prompt(update: PromptUpdate, user_id: str = Depends(get_current_user)):
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
def rate_post(request: RateRequest, user_id: str = Depends(get_current_user)):
    """Stores a rating for a historical post."""
    save_rating(
        post_text=sanitize_text(request.post_text),
        format_key=sanitize_text(request.format_key),
        rating=request.rating,
        timestamp=request.timestamp
    )
    return {"success": True}


@router.get("/formats")
def get_formats(user_id: str = Depends(get_current_user)):
    """Returns available post format keys and their display labels."""
    definitions = load_prompt_definitions()
    return {"formats": {k: v["label"] for k, v in definitions.items()}}


@router.get("/settings/plan")
def get_plan(user_id: str = Depends(get_current_user)):
    settings = _settings_for_user(user_id)
    preferred = settings.get("preferred_providers") or {}
    return {"plan": preferred.get("twitter_plan", get_twitter_plan())}


@router.put("/settings/plan")
def update_plan(update: PlanUpdate, user_id: str = Depends(get_current_user)):
    plan = sanitize_text(update.plan).lower()
    settings = _settings_for_user(user_id)
    preferred = settings.get("preferred_providers") or {}
    preferred["twitter_plan"] = plan
    _update_settings_for_user(user_id, {"preferred_providers": preferred})
    return {"success": True}


@router.get("/settings")
def get_all_settings(user_id: str = Depends(get_current_user)):
    return _settings_for_user(user_id)


@router.post("/settings/sprint/toggle")
def sprint_toggle(user_id: str = Depends(get_current_user)):
    settings = _settings_for_user(user_id)
    new_state = not bool(settings.get("sprint_mode"))
    _update_settings_for_user(user_id, {"sprint_mode": new_state})
    return {"success": True, "sprint_mode": new_state}


@router.get("/settings/keys")
def get_keys_status(user_id: str = Depends(get_current_user)):
    return get_ai_keys_status(user_id)


@router.post("/article/generate")
@limiter.limit("5/minute")
async def generate_article(request: Request, body: ArticleGenerateRequest, user_id: str = Depends(get_current_user)):
    """Generates a full technical article from sprint context."""
    if not CURRENT_DRAFT.exists():
        raise HTTPException(status_code=400, detail="No active draft to generate article from.")

    try:
        with open(CURRENT_DRAFT, "r", encoding="utf-8") as f:
            draft = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading draft: {e}")

    codebase_summary = ""
    if body.include_codebase:
        codebase_summary = summarise_for_prompt(sanitize_text(body.repo_path))

    # Use Article prompt
    sys_prompt = article_prompt(codebase_summary)
    
    # Context from draft and sprint log
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
async def refine_article(request: ArticleRefineRequest, user_id: str = Depends(get_current_user)):
    """Refines an article draft based on user instructions."""
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
def get_patterns(user_id: str = Depends(get_current_user)):
    """Returns all available viral patterns."""
    return get_all_patterns()


@router.post("/thread/split")
def thread_split(request: ThreadSplitRequest, user_id: str = Depends(get_current_user)):
    """Splits a long post into a numbered thread."""
    tweets = split_into_thread(sanitize_text(request.post_text))
    return {"success": True, "tweets": tweets}


@router.post("/posts/verify")
def verify_logged_post(request: PostVerifyRequest, user_id: str = Depends(get_current_user)):
    post_id = sanitize_text(request.post_id)
    post_url = sanitize_text(request.post_url or "")
    result = verify_post(post_id, post_url, user_id=user_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "post not found"))
    track("post_verified", {"has_url": bool(post_url)})
    return {"success": True}


@router.post("/posts/decline")
def decline_logged_post(request: PostDeclineRequest, user_id: str = Depends(get_current_user)):
    result = decline_post(sanitize_text(request.post_id), user_id=user_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "post not found"))
    return {"success": True}


@router.get("/posts/unverified")
def unverified_posts(user_id: str = Depends(get_current_user)):
    return {"posts": get_unverified_posts(user_id)}


@router.post("/metrics/save")
def save_post_metrics(request: MetricsSaveRequest, user_id: str = Depends(get_current_user)):
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

    result = save_metrics(
        sanitize_text(request.post_id),
        {
            **values,
            "hashtags": hashtags,
            "platform": sanitize_text(request.platform or ""),
        },
        user_id=user_id,
    )
    invalidate_insights_cache()
    track("metrics_saved", {"days_after": request.days_after_post})
    return result


@router.get("/metrics/{post_id}")
def get_post_metrics(post_id: str, user_id: str = Depends(get_current_user)):
    return get_metrics(sanitize_text(post_id), user_id=user_id)


@router.get("/insights")
def get_insights(user_id: str = Depends(get_current_user)):
    now = time.time()
    cache_key = f"data:{user_id}"
    if _INSIGHTS_CACHE.get(cache_key) is not None and now - _INSIGHTS_CACHE["timestamp"] < 3600:
        return _INSIGHTS_CACHE[cache_key]
    data = calculate_insights(user_id)
    _INSIGHTS_CACHE["timestamp"] = now
    _INSIGHTS_CACHE[cache_key] = data
    return data
