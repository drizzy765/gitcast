from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from ai.generator import generate_posts, generate_sprint_summary, _groq_call
from ai.prompts import load_prompt_definitions, PROMPTS_FILE, article_prompt, article_refinement_prompt
from ai.formatter import split_into_thread
from ai.viral_patterns import get_all_patterns
from api.payload import validate_payload
from api.auth import verify_token
from storage.logger import load_posts
from storage.tone_memory import save_rating
from core.codebase_reader import summarise_for_prompt
from config.settings import get_twitter_plan, set_twitter_plan, validate_api_keys, CURRENT_DRAFT, SPRINT_LOG
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


class PlanUpdate(BaseModel):
    plan: str


class KeysUpdate(BaseModel):
    twitter_api_key: Optional[str] = None
    twitter_api_secret: Optional[str] = None
    twitter_access_token: Optional[str] = None
    twitter_access_secret: Optional[str] = None
    twitter_bearer_token: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    format_key: str


class CliTriggerRequest(BaseModel):
    thought: str


class ArticleGenerateRequest(BaseModel):
    include_codebase: Optional[bool] = False
    repo_path: Optional[str] = "."


class ArticleRefineRequest(BaseModel):
    current_article: str
    instruction: str


class ThreadSplitRequest(BaseModel):
    post_text: str


# ── Routes ────────────────────────────────────────────────────────────────────

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
        new_text = await _groq_call(
            system_prompt=refinement_system_prompt,
            user_message=refinement_user_message
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
        f"Raw Thoughts: {draft['payload']['user_message']}\n\n"
        f"OCR Context: {draft['payload']['ocr_text']}\n\n"
        f"Git Diff: {draft['payload']['git_diff']}\n\n"
        f"Sprint Context: {sprint_context}"
    )

    try:
        article = await _groq_call(system_prompt=sys_prompt, user_message=user_msg)
        return {"success": True, "article": article}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Article generation failed: {e}")


@router.post("/article/refine", dependencies=[Depends(verify_token)])
async def refine_article(request: ArticleRefineRequest):
    """Refines an article draft based on user instructions."""
    sys_prompt = article_refinement_prompt(request.current_article, request.instruction)
    try:
        article = await _groq_call(system_prompt=sys_prompt, user_message="Refine the article.")
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
