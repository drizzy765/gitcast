import base64
from pathlib import Path
from config.settings import get_project_narrative
from core.log_stream import stream_log


# ── Payload builder ───────────────────────────────────────────────────────────

def build_payload(
    raw_thought: str,
    ocr_result: dict,
    capture_result: dict,
    format_keys: list = None,
    multi_screenshots: list = None,
) -> dict:
    """
    Assembles the full payload from all captured context.
    Supports single or multi-screenshot sessions.
    """
    if format_keys is None:
        format_keys = ["deep_tech", "struggle", "quick_win", "pr_generator"]

    narrative = get_project_narrative()
    git_diff = capture_result.get("git_diff", {"diff": "", "success": False})
    
    # Handle single or multi-shot
    if multi_screenshots:
        screenshots = multi_screenshots
        primary_shot = screenshots[0]
    else:
        # Normalize single shot to a list of one
        primary_shot = capture_result["screenshot"]
        screenshots = [{
            "path": primary_shot["path"],
            "purpose": "general",
            "ocr_text": ocr_result.get("text") or ocr_result.get("raw_text", ""),
            "confidence": ocr_result.get("confidence", 0.0),
            "timestamp": primary_shot.get("timestamp", ""),
            "index": 1
        }]

    # Decide vision fallback based on primary shot or all shots
    # For now, we'll use OCR if any shot is reliable, but usually it's per-shot.
    # LLM will see OCR text for each shot.
    use_vision = ocr_result.get("use_vision_fallback", False) if not multi_screenshots else False

    # encode primary screenshot as base64 for vision fallback
    screenshot_b64 = None
    if use_vision and primary_shot.get("path"):
        screenshot_b64 = _encode_image(primary_shot["path"])

    # build the structured user message
    user_message = _build_user_message(
        raw_thought=raw_thought,
        screenshots=screenshots,
        git_diff=git_diff,
        narrative=narrative,
        use_vision=use_vision,
    )

    # joined OCR text for legacy/summary access
    all_ocr = "\n\n".join([s.get("ocr_text", "") for s in screenshots if s.get("ocr_text")])

    stream_log(
        "Payload",
        "OK",
        f"assembled payload: {len(screenshots)} screenshot(s), {len(all_ocr)} OCR chars",
    )

    return {
        "raw_thought": raw_thought.strip(),
        "ocr_text": all_ocr,
        "screenshots": screenshots,
        "git_diff": git_diff.get("diff", ""),
        "git_diff_available": git_diff.get("success", False) and bool(git_diff.get("diff")),
        "narrative": narrative,
        "use_vision_fallback": use_vision,
        "screenshot_b64": screenshot_b64,
        "screenshot_path": primary_shot.get("path", ""),
        "user_message": user_message,
        "format_keys": format_keys,
        "timestamp": primary_shot.get("timestamp", ""),
        "working_dir": capture_result.get("working_dir", ""),
    }


# ── User message builder ──────────────────────────────────────────────────────

def _build_user_message(
    raw_thought: str,
    screenshots: list,
    git_diff: dict,
    narrative: str,
    use_vision: bool,
) -> str:
    """
    Builds the user-turn message that gets sent to the LLM.
    Structures multiple screenshots with their purpose tags.
    """
    parts = []
    parts.append("Here is the context for this build update:\n")

    # developer's raw thought
    if raw_thought.strip():
        parts.append(f"## Developer's raw thought\n{raw_thought.strip()}")

    # Screenshots with Purpose Tags and OCR
    parts.append("## Screen context")
    for s in screenshots:
        idx = s.get("index", 1)
        purpose = s.get("purpose", "general")
        parts.append(f"### Screenshot {idx} ({purpose})")
        
        ocr = s.get("ocr_text", "").strip()
        if ocr:
            parts.append(f"Visible text:\n{ocr}")
        else:
            parts.append("[No text detected or OCR failed]")

    # git diff
    diff_text = git_diff.get("diff", "") if isinstance(git_diff, dict) else ""
    if diff_text:
        parts.append(f"## Git diff (recent code changes)\n```\n{diff_text.strip()}\n```")

    # project narrative
    if narrative:
        parts.append(f"## Project context\n{narrative}")

    parts.append(
        "\nUsing the context above, generate the post now. "
        "Follow the format and rules in the system prompt exactly."
    )

    return "\n\n".join(parts)


# ── Sprint Mode payload ───────────────────────────────────────────────────────

def build_sprint_payload(sprint_log_entries: list) -> dict:
    """
    Builds the payload for Sprint Mode — takes the full list of
    silent captures and assembles them into one batched message
    for the sprint summary prompt.
    """
    parts = ["You have been given a log of captures from a coding sprint.\n"]

    for i, entry in enumerate(sprint_log_entries, 1):
        parts.append(f"--- Capture {i} of {len(sprint_log_entries)} ---")

        if entry.get("raw_thought"):
            parts.append(f"Developer thought: {entry['raw_thought']}")

        if entry.get("git_diff"):
            parts.append(f"Code changes:\n```\n{entry['git_diff'][:500]}\n```")

        if entry.get("ocr_text"):
            parts.append(f"Screen context: {entry['ocr_text'][:300]}")

        if entry.get("timestamp"):
            parts.append(f"Time: {entry['timestamp']}")

    parts.append(
        "\nSynthesize all of the above into a compelling sprint thread. "
        "Follow the format and rules in the system prompt exactly."
    )

    narrative = get_project_narrative()

    return {
        "user_message": "\n\n".join(parts),
        "format_keys": ["sprint_summary"],
        "narrative": narrative,
        "num_captures": len(sprint_log_entries),
        "use_vision_fallback": False,
        "screenshot_b64": None,
    }


# ── Image encoder ─────────────────────────────────────────────────────────────

def _encode_image(image_path: str) -> str:
    """
    Encodes an image file as a base64 string for the Gemini vision API.
    Returns empty string if encoding fails.
    """
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        stream_log("Payload", "WARN", f"image encoding failed: {e}")
        return ""


# ── Payload validator ─────────────────────────────────────────────────────────

def validate_payload(payload: dict) -> tuple[bool, list[str]]:
    """
    Checks the payload has the minimum viable content to generate a post.
    Returns (is_valid, list_of_warnings).
    """
    warnings = []

    if not payload.get("raw_thought"):
        warnings.append("No raw thought provided — post quality will be lower.")

    if not payload.get("git_diff_available"):
        warnings.append("No git diff — post will rely on OCR and raw thought only.")

    if not payload.get("ocr_text") and not payload.get("use_vision_fallback"):
        warnings.append("No OCR text and no vision fallback — very limited context.")

    if not payload.get("narrative"):
        warnings.append("No project narrative set — posts will lack mission context.")

    # payload is valid as long as there's at least a raw thought
    is_valid = bool(payload.get("raw_thought"))

    return is_valid, warnings


# ── Test ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from core.capture import run_capture
    from core.ocr import run_ocr
    from config.settings import set_project_narrative

    # set a test narrative
    set_project_narrative("an AI-powered build-in-public automation tool for developers")

    print("[Payload] Running capture pipeline...")
    capture = run_capture()
    ocr = run_ocr(capture["screenshot"]["path"])

    payload = build_payload(
        raw_thought="just got OCR working and it's reading the screen reliably",
        ocr_result=ocr,
        capture_result=capture,
    )

    is_valid, warnings = validate_payload(payload)

    print("\n=== PAYLOAD RESULT ===")
    print(f"Valid:              {is_valid}")
    print(f"Warnings:           {warnings if warnings else 'none'}")
    print(f"Raw thought:        {payload['raw_thought']}")
    print(f"OCR text length:    {len(payload['ocr_text'])} chars")
    print(f"Git diff available: {payload['git_diff_available']}")
    print(f"Use vision:         {payload['use_vision_fallback']}")
    print(f"Narrative:          {payload['narrative']}")
    print(f"Format keys:        {payload['format_keys']}")
    print(f"\nUser message preview:")
    print(payload["user_message"][:600])
