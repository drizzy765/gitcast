import uuid

from config.settings import CONFIG_DIR, POSTHOG_API_KEY


ANONYMOUS_ID_FILE = CONFIG_DIR / "anonymous_id.txt"
SENSITIVE_KEYS = {"post_text", "ocr_text", "git_diff", "screenshot_path", "api_key", "key", "raw_thought"}


def _anonymous_id() -> str:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if ANONYMOUS_ID_FILE.exists():
        value = ANONYMOUS_ID_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value

    value = str(uuid.uuid4())
    ANONYMOUS_ID_FILE.write_text(value, encoding="utf-8")
    return value


ANONYMOUS_ID = _anonymous_id()


def _clean_properties(properties: dict) -> dict:
    cleaned = {}
    for key, value in (properties or {}).items():
        if key in SENSITIVE_KEYS:
            continue
        cleaned[key] = value
    return cleaned


def track(event: str, properties: dict = {}) -> None:
    if not POSTHOG_API_KEY:
        return

    try:
        import posthog

        posthog.project_api_key = POSTHOG_API_KEY
        posthog.capture(ANONYMOUS_ID, event, _clean_properties(properties))
    except Exception:
        return


if __name__ == "__main__":
    print(f"[Analytics] Anonymous ID: {ANONYMOUS_ID}")
