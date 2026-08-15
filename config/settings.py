import json
import os
from pathlib import Path

from dotenv import load_dotenv


import sys

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"

def get_env_paths() -> list:
    paths = []
    # 1. Custom env path
    custom_path = os.getenv("GITCAST_ENV_PATH")
    if custom_path:
        paths.append(Path(custom_path))
    # 2. Current working directory
    paths.append(Path(os.getcwd()) / ".env")
    # 3. Virtual environment parent
    if hasattr(sys, "prefix") and sys.prefix:
        paths.append(Path(sys.prefix).parent / ".env")
    # 4. User home directories
    paths.append(Path.home() / ".gitcast" / ".env")
    paths.append(Path.home() / ".gitcast.env")
    # 5. Base directory
    paths.append(BASE_DIR / ".env")
    return [p for p in paths if p]

def load_all_dotenvs(override: bool = False) -> None:
    paths = get_env_paths()
    if override:
        for p in reversed(paths):
            if p.exists() and p.is_file():
                load_dotenv(p, override=True)
    else:
        for p in paths:
            if p.exists() and p.is_file():
                load_dotenv(p, override=False)

def get_active_env_path(for_write: bool = False) -> Path:
    paths = get_env_paths()
    for p in paths:
        if p.exists() and p.is_file():
            return p
    if for_write:
        home_env = Path.home() / ".gitcast" / ".env"
        try:
            home_env.parent.mkdir(parents=True, exist_ok=True)
            return home_env
        except Exception:
            pass
    return BASE_DIR / ".env"

load_all_dotenvs()
STORAGE_DIR = BASE_DIR / "storage" / "data"

# create on import so it always exists
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "screenshots").mkdir(
    parents=True, exist_ok=True)

POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY", "")
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
WAITLIST_FILE = STORAGE_DIR / "waitlist.txt"
METRICS_LOG = STORAGE_DIR / "metrics_log.json"
PROMPTS_FILE = STORAGE_DIR / "prompts.json"
CURRENT_DRAFT = STORAGE_DIR / "current_draft.json"
SPRINT_LOG = STORAGE_DIR / "sprint_log.txt"
POST_LOG = STORAGE_DIR / "post_log.json"
TONE_LOG = STORAGE_DIR / "tone_log.json"
ENGAGEMENT_LOG = STORAGE_DIR / "engagement_log.json"
ENCRYPTION_KEY_PATH = CONFIG_DIR / ".secret_key"
SETTINGS_FILE = CONFIG_DIR / "user_settings.json"
screenshot_retention_hours = 24

BYOK_KEY = os.getenv("BYOK_KEY", "")
BYOK_PROVIDER = os.getenv("BYOK_PROVIDER", "groq")
GITCAST_API_URL = os.getenv("GITCAST_API_URL", "https://gitcast-api.onrender.com")


API_KEY_ENV_MAP = {
    "byok": "BYOK_KEY",
    "byok_provider": "BYOK_PROVIDER",
}

USING_BASE_KEYS = False


def reload_api_keys() -> None:
    global BYOK_KEY
    global BYOK_PROVIDER
    global GITCAST_API_URL
    global USING_BASE_KEYS

    load_all_dotenvs(override=True)

    BYOK_KEY = os.getenv("BYOK_KEY", "")
    BYOK_PROVIDER = os.getenv("BYOK_PROVIDER", "groq")
    GITCAST_API_URL = os.getenv("GITCAST_API_URL", "https://gitcast-api.onrender.com")
    USING_BASE_KEYS = not bool(BYOK_KEY)


reload_api_keys()

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


def get_project_narrative(directory: str = None) -> str:
    cwd_key = str(Path(directory or os.getcwd()).resolve())
    narratives = load_settings().get("project_narratives", {})
    if isinstance(narratives, dict) and cwd_key in narratives:
        return str(narratives[cwd_key]).strip()
    return ""


def set_project_narrative(narrative: str, directory: str = None) -> None:
    cwd_key = str(Path(directory or os.getcwd()).resolve())
    settings = load_settings()
    narratives = settings.get("project_narratives", {})
    if not isinstance(narratives, dict):
        narratives = {}
    narratives[cwd_key] = narrative.strip()
    settings["project_narratives"] = narratives
    settings["project_narrative"] = narrative.strip()
    save_settings(settings)


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
        "byok_key": bool(BYOK_KEY),
        "twitter_api_key": bool(TWITTER_API_KEY),
        "twitter_api_secret": bool(TWITTER_API_SECRET),
        "twitter_access_token": bool(TWITTER_ACCESS_TOKEN),
        "twitter_access_secret": bool(TWITTER_ACCESS_SECRET),
        "twitter_bearer_token": bool(TWITTER_BEARER_TOKEN),
    }


def missing_api_keys() -> list:
    return [key for key, present in validate_api_keys().items() if not present and key != "byok_key"]


def ai_provider_key_status() -> dict:
    return {
        provider: bool(os.getenv(env_name, "").strip())
        for provider, env_name in API_KEY_ENV_MAP.items()
    }

