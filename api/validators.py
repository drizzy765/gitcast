import logging
import re
from pathlib import Path

from fastapi import HTTPException

from config.settings import BASE_DIR, STORAGE_DIR


CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
HTML_TAGS = re.compile(r"<[^>]*>")
EMAIL_REGEX = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)
INJECTION_PATTERNS = [
    "ignore previous instructions",
    "ignore all instructions",
    "system prompt",
    "you are now",
    "disregard",
    "forget everything",
    "new instructions",
]


def sanitize_text(text: str) -> str:
    if text is None:
        return ""
    clean = str(text).strip()
    clean = CONTROL_CHARS.sub("", clean)
    clean = HTML_TAGS.sub("", clean)
    return clean[:2000]


def sanitize_path(path: str) -> str:
    if not path:
        return ""

    raw = str(path).strip()
    if re.search(r"(^|[\\/])\.\.([\\/]|$)", raw) or raw in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid path traversal attempt")

    storage_root = STORAGE_DIR.resolve()
    candidate = Path(raw)
    if not candidate.is_absolute():
        if raw.replace("\\", "/").startswith("storage/"):
            candidate = (BASE_DIR / raw).resolve()
        else:
            candidate = (storage_root / raw).resolve()
    else:
        candidate = candidate.resolve()

    try:
        candidate.relative_to(storage_root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path must stay within storage directory")

    return str(candidate)


def validate_email(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_api_key(key: str, provider: str) -> bool:
    value = (key or "").strip()
    name = (provider or "").strip().lower()
    if not value:
        return False

    if name == "groq":
        return value.startswith("gsk_") and len(value) >= 40
    if name == "gemini":
        return len(value) >= 30
    if name == "openai":
        return value.startswith("sk-") and len(value) >= 40
    return len(value) >= 20


def check_prompt_injection(text: str) -> dict:
    raw = text or ""
    lowered = raw.lower()
    flagged = [phrase for phrase in INJECTION_PATTERNS if phrase in lowered]
    if not flagged:
        return {"safe": True, "reason": ""}

    logging.warning("[Validators] prompt injection phrase(s) removed: %s", ", ".join(flagged))
    sanitized = raw
    for phrase in flagged:
        sanitized = re.sub(re.escape(phrase), "", sanitized, flags=re.IGNORECASE)

    return {
        "safe": False,
        "reason": f"Removed prompt injection phrase(s): {', '.join(flagged)}",
        "sanitized": sanitize_text(sanitized),
    }


if __name__ == "__main__":
    print("[Validators] email valid:", validate_email("founder@example.com"))
    print("[Validators] clean:", sanitize_text(" <b>hello</b>\x00 "))
