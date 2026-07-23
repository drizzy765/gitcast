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
    project_ctx: dict = None,
) -> dict:
    """
    Assembles the full payload from all captured context.
    Supports single or multi-screenshot sessions.
    """
    if format_keys is None:
        format_keys = ["deep_tech", "linkedin", "pr_generator", "quick_win"]

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
    use_vision = ocr_result.get("use_vision_fallback", False) if not multi_screenshots else False

    # encode primary screenshot as base64 for vision fallback
    screenshot_b64 = None
    if use_vision and primary_shot.get("path"):
        screenshot_b64 = _encode_image(primary_shot["path"])

    # joined OCR text for legacy/summary access
    all_ocr = "\n\n".join([s.get("ocr_text", "") for s in screenshots if s.get("ocr_text")])

    payload = {
        "raw_thought": raw_thought.strip(),
        "ocr_text": all_ocr,
        "screenshots": screenshots,
        "git_diff": git_diff.get("diff", ""),
        "git_diff_available": git_diff.get("success", False) and bool(git_diff.get("diff")),
        "narrative": narrative,
        "use_vision_fallback": use_vision,
        "screenshot_b64": screenshot_b64,
        "screenshot_path": primary_shot.get("path", ""),
        "format_keys": format_keys,
        "timestamp": primary_shot.get("timestamp", ""),
        "working_dir": capture_result.get("working_dir", ""),
    }

    if project_ctx:
        payload["project_name"] = project_ctx.get("project_name", "")
        payload["readme_content"] = project_ctx.get("readme_content", "")
        payload["tech_stack"] = project_ctx.get("tech_stack", "")
        payload["project_type"] = project_ctx.get("project_type", "")
        payload["main_language"] = project_ctx.get("main_language", "")

    # build the structured user message
    user_message = _build_user_message(
        raw_thought=raw_thought,
        screenshots=screenshots,
        git_diff=git_diff,
        narrative=narrative,
        use_vision=use_vision,
        payload=payload,
    )
    payload["user_message"] = user_message

    stream_log(
        "Payload",
        "OK",
        f"assembled payload: {len(screenshots)} screenshot(s), {len(all_ocr)} OCR chars",
    )

    return payload


# ── User message builder ──────────────────────────────────────────────────────

def _build_user_message(
    raw_thought: str,
    screenshots: list,
    git_diff: dict,
    narrative: str,
    use_vision: bool,
    payload: dict = None,
) -> str:
    """
    Builds the user-turn message that gets sent to the LLM.
    Structures multiple screenshots with their purpose tags.
    """
    if payload is None:
        payload = {}

    parts = []
    parts.append("Here is the context for this build update:\n")

    # developer's raw thought
    if raw_thought.strip():
        parts.append(f"## Developer's raw thought\n{raw_thought.strip()}")

    # git diff section comes first
    diff_text = git_diff.get("diff", "") if isinstance(git_diff, dict) else ""
    if diff_text:
        parts.append(f"## Git diff (primary source)\n```\n{diff_text.strip()}\n```")

    # check if OCR text is fragmented
    ocr_text = "\n\n".join([s.get("ocr_text", "") for s in screenshots if s.get("ocr_text")]).strip()

    # OCR section comes second, clearly labeled
    if ocr_text and not use_vision:
        parts.append(
            f"## Screen text (secondary, may be noisy)\n"
            f"{ocr_text.strip()}"
        )

    narrative = payload.get("narrative", "").strip()
    readme = payload.get("readme_content", "").strip()
    tech_stack = payload.get("tech_stack", "").strip()
    project_name = payload.get(
        "project_name", "").strip()

    if narrative or readme or tech_stack:
        context_lines = [
            "## BACKGROUND (use to understand the "
            "project — do NOT reproduce these headers "
            "or this section in your output):"
        ]
        if project_name:
            context_lines.append(
                f"Project name: {project_name}")
        if tech_stack:
            context_lines.append(
                f"Tech stack: {tech_stack}")
        if narrative:
            # strip markdown headers from narrative
            # before injecting so they don't leak
            clean_narrative = "\n".join(
                line for line in narrative.splitlines()
                if not line.strip().startswith("#")
            )
            context_lines.append(
                f"Project description: {clean_narrative[:600]}")
        if readme:
            # extract first 400 chars of README
            # skip any markdown headers
            clean_readme = "\n".join(
                line for line in readme.splitlines()
                if not line.strip().startswith("#")
                and line.strip()
            )
            context_lines.append(
                f"README summary: {clean_readme[:400]}")

        parts.append("\n".join(context_lines))

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
        from config.settings import BASE_DIR
        path = Path(image_path)
        if not path.is_absolute():
            path = BASE_DIR / path
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        stream_log("Payload", "WARN", f"image encoding failed: {e}")
        return ""


# ── Payload validator ─────────────────────────────────────────────────────────

GENERIC_THOUGHTS = [
    "captured via hotkey trigger",
    "",
    "test",
    "testing",
    "...",
    "thought",
]

def validate_payload(payload: dict) -> tuple[bool, list[str]]:
    """
    Checks the payload has the minimum viable content to generate a post.
    Returns (is_valid, list_of_warnings).
    """
    warnings = []

    raw_thought = payload.get("raw_thought", "").strip()
    ocr_text = payload.get("ocr_text", "").strip()
    git_diff = payload.get("git_diff", "").strip()
    git_diff_available = payload.get("git_diff_available", False)

    is_generic_thought = (
        raw_thought.lower() in GENERIC_THOUGHTS or
        len(raw_thought) < 5
    )
    has_real_ocr = len(ocr_text) >= 80
    has_diff = git_diff_available and len(git_diff) > 20

    # BLOCK generation if all three are weak
    if is_generic_thought and not has_real_ocr and not has_diff:
        return False, [
            "Not enough context to generate a post. Please:\n"
            "1. Capture from your code editor (not a browser)\n"
            "2. Type a real thought about what you just built or fixed\n"
            "3. Make sure you have uncommitted git changes for best results"
        ]

    # WARN but allow if thought is real but diff missing
    if not has_diff:
        warnings.append(
            "No git diff — post will rely on your thought and screen context only."
        )

    if not raw_thought or is_generic_thought:
        warnings.append(
            "Generic thought detected — post quality will be lower. Try describing what you actually fixed or built."
        )

    return True, warnings


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
