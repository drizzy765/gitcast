import json
from config.settings import SPRINT_LOG


def log_sprint_capture(
    git_diff: str,
    ocr_text: str,
    raw_thought: str,
    timestamp: str,
) -> None:
    entry = {
        "timestamp": timestamp,
        "raw_thought": raw_thought,
        "git_diff": git_diff[:1000],
        "ocr_text": ocr_text[:500],
    }
    with open(SPRINT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[Sprint] Capture logged to {SPRINT_LOG}")


def load_sprint_log() -> list[dict]:
    if not SPRINT_LOG.exists():
        return []
    entries = []
    with open(SPRINT_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def clear_sprint_log() -> None:
    if SPRINT_LOG.exists():
        SPRINT_LOG.unlink()
    print("[Sprint] Sprint log cleared.")
