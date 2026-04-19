from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from ai.generator import generate_posts, generate_sprint_summary
from api.payload import validate_payload

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
    format_keys: Optional[list[str]] = ["deep_tech", "struggle", "quick_win", "pr_generator"]
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
    variations: list[PostVariation]
    warnings: list[str]
    timestamp: str


class SprintRequest(BaseModel):
    entries: list[dict]
    narrative: Optional[str] = ""


# ── Format labels (shown in the UI tabs) ─────────────────────────────────────

FORMAT_LABELS = {
    "deep_tech": "Deep Tech",
    "struggle": "The Struggle",
    "quick_win": "Quick Win",
    "pr_generator": "PR Description",
    "sprint_summary": "Sprint Thread",
}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """
    Main generation endpoint.
    Receives the assembled payload and returns post variations.
    """
    payload = request.dict()

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

    variations = []
    for format_key, content in results.items():
        is_error = content.startswith("[Error]")
        variations.append(PostVariation(
            format_key=format_key,
            label=FORMAT_LABELS.get(format_key, format_key),
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


@router.post("/generate/sprint")
async def generate_sprint(request: SprintRequest):
    """
    Sprint Mode endpoint.
    Takes the full batch log and returns a synthesised thread.
    """
    if not request.entries:
        raise HTTPException(status_code=400, detail="No sprint entries provided.")

    try:
        result = await generate_sprint_summary(request.entries, request.narrative)
        return {"success": True, "thread": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/formats")
def get_formats():
    """Returns available post format keys and their display labels."""
    return {"formats": FORMAT_LABELS}