import asyncio
import httpx
from ai.prompts import get_all_prompts, sprint_summary_prompt
from config.settings import GROQ_API_KEY, GEMINI_API_KEY

# ── Constants ─────────────────────────────────────────────────────────────────

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama3-70b-8192"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
MAX_TOKENS = 1024
TIMEOUT = 30


# ── Main generator ────────────────────────────────────────────────────────────

async def generate_posts(payload: dict) -> dict[str, str]:
    """
    Fires all post format completions in parallel.
    Routes to Gemini vision if OCR fallback is flagged.
    Returns a dict of format_key → generated content.
    """
    prompts = get_all_prompts()
    format_keys = payload.get("format_keys", list(prompts.keys()))
    user_message = payload.get("user_message", "")
    use_vision = payload.get("use_vision_fallback", False)
    screenshot_b64 = payload.get("screenshot_b64", None)

    # filter to only requested formats
    selected_prompts = {k: v for k, v in prompts.items() if k in format_keys}

    tasks = []
    keys = []

    for format_key, system_prompt in selected_prompts.items():
        if use_vision and screenshot_b64:
            task = _gemini_vision_call(
                system_prompt=system_prompt,
                user_message=user_message,
                screenshot_b64=screenshot_b64,
            )
        else:
            task = _groq_call(
                system_prompt=system_prompt,
                user_message=user_message,
            )
        tasks.append(task)
        keys.append(format_key)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    output = {}
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            output[key] = f"[Error] {str(result)}"
        else:
            output[key] = result

    return output


async def generate_sprint_summary(entries: list[dict], narrative: str = "") -> str:
    """Generates a sprint thread from a batch of silent captures."""
    from api.payload import build_sprint_payload
    sprint_payload = build_sprint_payload(entries)
    system_prompt = sprint_summary_prompt(len(entries))
    user_message = sprint_payload["user_message"]

    return await _groq_call(
        system_prompt=system_prompt,
        user_message=user_message,
    )


# ── Groq call ─────────────────────────────────────────────────────────────────

async def _groq_call(system_prompt: str, user_message: str) -> str:
    """
    Single async call to Groq API.
    Uses llama3-70b — fast, cheap, excellent for structured text output.
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set in .env")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": GROQ_MODEL,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.85,  # slight creativity without going off-rails
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(GROQ_URL, headers=headers, json=body)
        if response.status_code != 200:
            print(f"[Groq Error] Status: {response.status_code}")
            print(f"[Groq Error] Body: {response.text}")
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

# ── Gemini vision call ────────────────────────────────────────────────────────

async def _gemini_vision_call(
    system_prompt: str,
    user_message: str,
    screenshot_b64: str,
) -> str:
    """
    Calls Gemini 1.5 Flash with the screenshot as a vision input.
    Used when OCR confidence is too low to extract reliable text.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in .env")

    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"

    body = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_prompt}\n\n{user_message}"},
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": screenshot_b64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": MAX_TOKENS,
            "temperature": 0.85,
        },
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(GROQ_URL, headers=headers, json=body)
        if response.status_code != 200:
            print(f"[Groq Error] Status: {response.status_code}")
            print(f"[Groq Error] Body: {response.text}")
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

# ── Test ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    from core.capture import run_capture
    from core.ocr import run_ocr
    from api.payload import build_payload
    from config.settings import set_project_narrative

    set_project_narrative("an AI-powered build-in-public automation tool for developers")

    async def test():
        print("[Generator] Running full pipeline test...")
        capture = run_capture()
        ocr = run_ocr(capture["screenshot"]["path"])
        payload = build_payload(
            raw_thought="just wired up the FastAPI server and generator — posts are about to be real",
            ocr_result=ocr,
            capture_result=capture,
        )

        print("[Generator] Firing parallel AI calls...")
        results = await generate_posts(payload)

        print("\n=== GENERATED POSTS ===")
        for format_key, content in results.items():
            print(f"\n--- {format_key.upper()} ---")
            print(content)
            print(f"({len(content)} chars)")

    asyncio.run(test())