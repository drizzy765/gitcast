import base64
from pathlib import Path
from config.settings import get_project_narrative


# ── Payload builder ───────────────────────────────────────────────────────────

def build_payload(
    raw_thought: str,
    ocr_result: dict,
    capture_result: dict,
    format_keys: list = None,
) -> dict:
    """
    Assembles the full payload from all captured context.
    This is the single dict that gets passed to the AI generator.

    Args:
        raw_thought:    The user's unformatted text from the popup.
        ocr_result:     Output from core/ocr.py run_ocr().
        capture_result: Output from core/capture.py run_capture().
        format_keys:    Which post formats to generate. Defaults to all four.
    """
    if format_keys is None:
        format_keys = ["deep_tech", "struggle", "quick_win", "pr_generator"]

    screenshot_path = capture_result["screenshot"]["path"]
    git_diff = capture_result["git_diff"]
    narrative = get_project_narrative()

    # decide whether to use OCR text or vision fallback
    use_vision = ocr_result.get("use_vision_fallback", False)
    ocr_text = ocr_result.get("text", "")

    # encode screenshot as base64 if vision fallback is needed
    screenshot_b64 = None
    if use_vision and screenshot_path:
        screenshot_b64 = _encode_image(screenshot_path)

    # build the user message content that goes into every prompt
    user_message = _build_user_message(
        raw_thought=raw_thought,
        ocr_text=ocr_text,
        git_diff=git_diff,
        narrative=narrative,
        use_vision=use_vision,
    )

    return {
        # core content
        "raw_thought": raw_thought.strip(),
        "ocr_text": ocr_text,
        "git_diff": git_diff.get("diff", ""),
        "git_diff_available": git_diff.get("success", False) and bool(git_diff.get("diff")),
        "narrative": narrative,

        # AI routing
        "use_vision_fallback": use_vision,
        "screenshot_b64": screenshot_b64,
        "screenshot_path": screenshot_path,
        "user_message": user_message,
        "format_keys": format_keys,

        # metadata
        "ocr_confidence": ocr_result.get("confidence", 0.0),
        "working_dir": capture_result.get("working_dir", ""),
        "timestamp": capture_result["screenshot"].get("timestamp", ""),
    }


# ── User message builder ──────────────────────────────────────────────────────

def _build_user_message(
    raw_thought: str,
    ocr_text: str,
    git_diff: dict,
    narrative: str,
    use_vision: bool,
) -> str:
    """
    Builds the user-turn message that gets sent to the LLM alongside
    the system prompt. Structures all context clearly so the model
    knows exactly what to work with.
    """
    parts = []

    parts.append("Here is the context for this build update:\n")

    # developer's raw thought — always present
    parts.append(f"## Developer's raw thought\n{raw_thought.strip()}")

    # OCR text from screenshot (if reliable)
    if ocr_text and not use_vision:
        parts.append(f"## Visible screen content (OCR)\n{ocr_text.strip()}")
    elif use_vision:
        parts.append("## Visible screen content\n[Screenshot attached — OCR confidence too low, use the image directly]")

    # git diff (if available)
    diff_text = git_diff.get("diff", "") if isinstance(git_diff, dict) else ""
    if diff_text:
        parts.append(f"## Git diff (recent code changes)\n```\n{diff_text.strip()}\n```")
    else:
        reason = git_diff.get("reason", "unknown") if isinstance(git_diff, dict) else "unknown"
        parts.append(f"## Git diff\n[Not available — reason: {reason}]")

    # project narrative reminder (if set)
    if narrative:
        parts.append(f"## Project context\n{narrative}")

    parts.append(
        "\nUsing the context above, generate the post now. "
        "Follow the format and rules in the system prompt exactly."
    )

    return "\n\n".join(parts)


# ── Sprint Mode payload ───────────────────────────────────────────────────────

def build_sprint_payload(sprint_log_entries: list[dict]) -> dict:
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
        print(f"[Payload] Image encoding failed: {e}")
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