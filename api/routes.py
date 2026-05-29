import asyncio
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from dotenv import dotenv_values, load_dotenv, set_key, unset_key
from ai.generator import generate_posts, generate_sprint_summary, _ai_call
from ai.prompts import load_prompt_definitions, PROMPTS_FILE, article_prompt, article_refinement_prompt
from ai.formatter import split_into_thread
from ai.viral_patterns import get_all_patterns
from api.payload import validate_payload
from api.auth import verify_token
from storage.logger import load_posts
from storage.tone_memory import save_rating
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
    reload_api_keys,
)
from core.log_stream import get_logs_after, get_latest_log_id, stream_log
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
    project_narrative: str


class PublishRequest(BaseModel):
    post_text: str
    screenshot_path: Optional[str] = None


class WaitlistRequest(BaseModel):
    email: str


# ── Routes ────────────────────────────────────────────────────────────────────

import re
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

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


@router.get("/keys/status", dependencies=[Depends(verify_token)])
def get_ai_keys_status():
    values = dotenv_values(_env_path())
    return {
        provider: bool((values.get(env_name) or "").strip())
        for provider, env_name in API_KEY_ENV_MAP.items()
    }


@router.post("/keys/update", dependencies=[Depends(verify_token)])
def update_ai_key(request: ProviderKeyUpdate):
    provider = _normalize_provider(request.provider)
    key = request.key.strip()
    if not key:
        return {"success": False, "error": "API key cannot be empty"}

    env_name = API_KEY_ENV_MAP[provider]
    try:
        set_key(str(_env_path()), env_name, key)
        os.environ[env_name] = key
        _reload_key_runtime()
        stream_log("Keys", "OK", f"{provider} key updated")
        return {"success": True, "provider": provider}
    except Exception as e:
        stream_log("Keys", "ERROR", f"{provider} key update failed: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/keys/remove", dependencies=[Depends(verify_token)])
def remove_ai_key(request: ProviderKeyRemove):
    provider = _normalize_provider(request.provider)
    env_name = API_KEY_ENV_MAP[provider]
    try:
        unset_key(str(_env_path()), env_name)
        os.environ.pop(env_name, None)
        _reload_key_runtime()
        stream_log("Keys", "OK", f"{provider} key removed")
        return {"success": True}
    except Exception as e:
        stream_log("Keys", "ERROR", f"{provider} key removal failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/keys/guide", dependencies=[Depends(verify_token)])
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
    """Appends an email to the waitlist file."""
    email = request.email.strip()
    if not EMAIL_REGEX.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    from config.settings import STORAGE_DIR
    waitlist_dir = STORAGE_DIR / "data"
    waitlist_dir.mkdir(parents=True, exist_ok=True)
    waitlist_file = waitlist_dir / "waitlist.txt"
    
    try:
        with open(waitlist_file, "a", encoding="utf-8") as f:
            f.write(email + "\n")
        return {"success": True, "message": "you're on the list"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to append to waitlist: {e}")


@router.post("/settings", dependencies=[Depends(verify_token)])
def update_settings(update: SettingsUpdate):
    """Updates global project settings."""
    from config.settings import set_project_narrative
    set_project_narrative(update.project_narrative)
    return {"success": True}


@router.post("/publish", dependencies=[Depends(verify_token)])
async def publish(request: PublishRequest):
    """Publishes a post to X (Twitter)."""
    from publisher.twitter import publish_post
    try:
        result = publish_post(request.post_text, request.screenshot_path)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Publishing failed: {e}")


@router.delete("/screenshot/{filename}", dependencies=[Depends(verify_token)])
def delete_screenshot(filename: str):
    """Securely deletes a screenshot from disk."""
    from core.security import delete_capture
    from config.settings import STORAGE_DIR
    path = STORAGE_DIR / "screenshots" / filename
    delete_capture(str(path))
    return {"success": True}


@router.get("/screenshot/{filename}/framed", dependencies=[Depends(verify_token)])
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


@router.post("/generate", response_model=GenerateResponse, dependencies=[Depends(verify_token)])
async def generate(request: GenerateRequest):
    payload = request.dict()
    
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
        results = await generate_posts(payload)
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


@router.get("/history", dependencies=[Depends(verify_token)])
def get_history():
    """Returns the full history of published posts."""
    return {"history": load_posts()}


@router.get("/draft", dependencies=[Depends(verify_token)])
def get_current_draft():
    """Returns the latest captured draft from disk."""
    if not CURRENT_DRAFT.exists():
        return {"status": "empty"}
    
    try:
        with open(CURRENT_DRAFT, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading draft: {e}")


@router.post("/chat", dependencies=[Depends(verify_token)])
async def chat_refine(request: ChatRequest):
    """Refines a post variation using AI chat."""
    if not CURRENT_DRAFT.exists():
        raise HTTPException(status_code=400, detail="No active draft to refine.")

    try:
        with open(CURRENT_DRAFT, "r", encoding="utf-8") as f:
            draft = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading draft: {e}")

    # Build the refinement prompt
    current_text = draft["variations"].get(request.format_key, "")
    
    # Simple refinement instruction
    refinement_system_prompt = (
        "You are a social media manager helping a developer refine a post. "
        "The user will provide instructions on how to change an existing draft. "
        "Keep the same general format rules but apply the user's changes strictly."
    )
    
    refinement_user_message = (
        f"Original Context:\n{draft['payload']['user_message']}\n\n"
        f"Current Draft for '{request.format_key}':\n{current_text}\n\n"
        f"User Instruction: {request.message}\n\n"
        "Output ONLY the revised post text. No preamble."
    )

    try:
        # Use routing for the specific format_key
        new_text = await _ai_call(
            request.format_key,
            refinement_system_prompt,
            refinement_user_message
        )
        
        # Update and save
        draft["variations"][request.format_key] = new_text
        with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
            json.dump(draft, f, indent=4)
            
        return {"success": True, "new_text": new_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI refinement failed: {e}")


@router.post("/cli/trigger", dependencies=[Depends(verify_token)])
async def cli_trigger(request: CliTriggerRequest):
    """Triggers a capture workflow with a specific thought from the CLI."""
    from core.capture import run_capture
    from core.ocr import run_ocr
    from api.payload import build_payload
    from ai.generator import generate_posts
    
    try:
        capture = run_capture()
        ocr = run_ocr(capture["screenshot"]["path"])
        
        payload = build_payload(
            raw_thought=request.thought,
            ocr_result=ocr,
            capture_result=capture,
        )
        
        # force Groq
        payload["use_vision_fallback"] = False
        payload["screenshot_b64"] = None
        
        variations = await generate_posts(payload)
        
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


@router.post("/capture/trigger", dependencies=[Depends(verify_token)])
async def ui_trigger_capture(request: CaptureTriggerRequest):
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
        
        variations = await generate_posts(payload)
        
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


@router.get("/screenshots", dependencies=[Depends(verify_token)])
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
    
    # Sort by newest first
    files.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"screenshots": files}


@router.post("/screenshot/recommend", dependencies=[Depends(verify_token)])
async def recommend_screenshot(request: RecommendRequest):
    """Uses AI to recommend where to post a specific screenshot."""
    from config.settings import STORAGE_DIR
    path = STORAGE_DIR / "screenshots" / request.filename
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
        recommendation = await _ai_call("deep_tech", system_prompt, f"Context: {ocr_context}")
        return {"success": True, "recommendation": recommendation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {e}")


@router.delete("/prompts/{format_key}", dependencies=[Depends(verify_token)])
def delete_prompt(format_key: str):
    """Deletes a prompt definition."""
    definitions = load_prompt_definitions()
    if format_key in definitions:
        del definitions[format_key]
        try:
            with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
                json.dump(definitions, f, indent=4)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=404, detail="Prompt not found")


@router.get("/prompts", dependencies=[Depends(verify_token)])
def get_prompts():
    """Returns all customizable prompt definitions."""
    return load_prompt_definitions()


@router.put("/prompts", dependencies=[Depends(verify_token)])
def update_prompt(update: PromptUpdate):
    """Updates a single prompt definition."""
    definitions = load_prompt_definitions()
    definitions[update.format_key] = {
        "label": update.label,
        "description": update.description,
        "system_prompt": update.system_prompt
    }
    
    try:
        with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
            json.dump(definitions, f, indent=4)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rate", dependencies=[Depends(verify_token)])
def rate_post(request: RateRequest):
    """Stores a rating for a historical post."""
    save_rating(
        post_text=request.post_text,
        format_key=request.format_key,
        rating=request.rating,
        timestamp=request.timestamp
    )
    return {"success": True}


@router.get("/formats", dependencies=[Depends(verify_token)])
def get_formats():
    """Returns available post format keys and their display labels."""
    definitions = load_prompt_definitions()
    return {"formats": {k: v["label"] for k, v in definitions.items()}}


@router.get("/settings/plan", dependencies=[Depends(verify_token)])
def get_plan():
    return {"plan": get_twitter_plan()}


@router.put("/settings/plan", dependencies=[Depends(verify_token)])
def update_plan(update: PlanUpdate):
    set_twitter_plan(update.plan)
    return {"success": True}


@router.get("/settings", dependencies=[Depends(verify_token)])
def get_all_settings():
    from config import settings
    return settings.load_settings()


@router.post("/settings/sprint/toggle", dependencies=[Depends(verify_token)])
def sprint_toggle():
    from config import settings
    new_state = settings.toggle_sprint_mode()
    return {"success": True, "sprint_mode": new_state}


@router.get("/settings/keys", dependencies=[Depends(verify_token)])
def get_keys_status():
    return validate_api_keys()


@router.post("/article/generate", dependencies=[Depends(verify_token)])
async def generate_article(request: ArticleGenerateRequest):
    """Generates a full technical article from sprint context."""
    if not CURRENT_DRAFT.exists():
        raise HTTPException(status_code=400, detail="No active draft to generate article from.")

    try:
        with open(CURRENT_DRAFT, "r", encoding="utf-8") as f:
            draft = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading draft: {e}")

    codebase_summary = ""
    if request.include_codebase:
        codebase_summary = summarise_for_prompt(request.repo_path)

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
        article = await _ai_call("article", sys_prompt, user_msg)
        return {"success": True, "article": article}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Article generation failed: {e}")


@router.post("/article/refine", dependencies=[Depends(verify_token)])
async def refine_article(request: ArticleRefineRequest):
    """Refines an article draft based on user instructions."""
    sys_prompt = article_refinement_prompt(request.current_article, request.instruction)
    try:
        article = await _ai_call("article", sys_prompt, "Refine the article.")
        return {"success": True, "article": article}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Article refinement failed: {e}")


@router.get("/patterns", dependencies=[Depends(verify_token)])
def get_patterns():
    """Returns all available viral patterns."""
    return get_all_patterns()


@router.post("/thread/split", dependencies=[Depends(verify_token)])
def thread_split(request: ThreadSplitRequest):
    """Splits a long post into a numbered thread."""
    tweets = split_into_thread(request.post_text)
    return {"success": True, "tweets": tweets}
