import json
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
STORAGE_DIR = BASE_DIR / "storage" / "data"
PROMPTS_FILE = STORAGE_DIR / "prompts.json"
CURRENT_DRAFT = STORAGE_DIR / "current_draft.json"
SPRINT_LOG = STORAGE_DIR / "sprint_log.txt"
POST_LOG = STORAGE_DIR / "post_log.json"
TONE_LOG = STORAGE_DIR / "tone_log.json"
ENGAGEMENT_LOG = STORAGE_DIR / "engagement_log.json"
ENCRYPTION_KEY_PATH = CONFIG_DIR / ".secret_key"
SETTINGS_FILE = CONFIG_DIR / "user_settings.json"
screenshot_retention_hours = 24

load_dotenv(BASE_DIR / ".env")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
MOONSHOT_API_KEY = os.getenv("MOONSHOT_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# ── AI Provider Routing ───────────────────────────────────────────────────────

# Maps format_key -> preferred provider alias
# Providers: 'groq', 'deepseek', 'moonshot', 'gemini'
AI_ROUTING_MAP = {
    "article": "moonshot",    # Better for long context
    "linkedin": "deepseek",   # Good reasoning
    "deep_tech": "deepseek",
    "shitpost": "groq",       # Fast
    "sprint_summary": "moonshot",
    "default": "groq"
}
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")


DEFAULTS = {
    "project_narrative": "",
    "sprint_mode": False,
    "tone_memory_enabled": True,
    "ocr_confidence_threshold": 60,
    "post_char_limit": 280,
    "twitter_plan": "free",
    "onboarding_complete": False,
}


def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULTS)
        return DEFAULTS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as file:
            stored = json.load(file)
        return {**DEFAULTS, **stored}
    except (json.JSONDecodeError, OSError):
        return DEFAULTS.copy()


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as file:
        json.dump(settings, file, indent=2)


def get(key: str):
    return load_settings().get(key, DEFAULTS.get(key))


def set(key: str, value) -> None:
    settings = load_settings()
    settings[key] = value
    save_settings(settings)


def get_project_narrative() -> str:
    return str(get("project_narrative") or "")


def set_project_narrative(narrative: str) -> None:
    set("project_narrative", narrative.strip())


def is_sprint_mode() -> bool:
    return bool(get("sprint_mode"))


def toggle_sprint_mode() -> bool:
    current = is_sprint_mode()
    set("sprint_mode", not current)
    return not current


def is_tone_memory_enabled() -> bool:
    return bool(get("tone_memory_enabled"))


def get_ocr_threshold() -> int:
    return int(get("ocr_confidence_threshold") or DEFAULTS["ocr_confidence_threshold"])


def get_tesseract_cmd() -> str:
    configured = os.getenv("TESSERACT_CMD", "").strip()
    if configured:
        return configured
    return "tesseract"


def is_onboarding_complete() -> bool:
    return bool(get("onboarding_complete"))


def complete_onboarding() -> None:
    set("onboarding_complete", True)


def get_twitter_plan() -> str:
    return str(get("twitter_plan") or "free")


def set_twitter_plan(plan: str) -> None:
    if plan.lower() in ["free", "basic", "premium"]:
        set("twitter_plan", plan.lower())


def validate_api_keys() -> dict:
    return {
        "groq": bool(GROQ_API_KEY),
        "deepseek": bool(DEEPSEEK_API_KEY),
        "moonshot": bool(MOONSHOT_API_KEY),
        "gemini": bool(GEMINI_API_KEY),
        "cerebras": bool(CEREBRAS_API_KEY),
        "openrouter": bool(OPENROUTER_API_KEY),
        "twitter_api_key": bool(TWITTER_API_KEY),
        "twitter_api_secret": bool(TWITTER_API_SECRET),
        "twitter_access_token": bool(TWITTER_ACCESS_TOKEN),
        "twitter_access_secret": bool(TWITTER_ACCESS_SECRET),
        "twitter_bearer_token": bool(TWITTER_BEARER_TOKEN),
    }


def missing_api_keys() -> list[str]:
    return [key for key, present in validate_api_keys().items() if not present]
