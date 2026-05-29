from collections import deque
from datetime import datetime
from threading import Lock


LOG_BUFFER = deque(maxlen=100)
_LOCK = Lock()
_NEXT_ID = 0
_LEVELS = {"OK", "INFO", "WARN", "ERROR", "AI", "ROUTER"}


def stream_log(module: str, level: str, message: str) -> dict:
    global _NEXT_ID

    normalized_level = level.upper().strip()
    if normalized_level not in _LEVELS:
        normalized_level = "INFO"

    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "level": normalized_level,
        "module": module.upper().strip(),
        "message": message.strip(),
    }

    with _LOCK:
        _NEXT_ID += 1
        stored = {"id": _NEXT_ID, **entry}
        LOG_BUFFER.append(stored)

    print(f"[{entry['module']}] {entry['message']}")
    return entry


def get_recent_logs() -> list:
    with _LOCK:
        return [
            {key: value for key, value in entry.items() if key != "id"}
            for entry in list(LOG_BUFFER)[-50:]
        ]


def get_logs_after(last_id: int) -> list:
    with _LOCK:
        return [entry.copy() for entry in LOG_BUFFER if entry["id"] > last_id]


def get_latest_log_id() -> int:
    with _LOCK:
        return LOG_BUFFER[-1]["id"] if LOG_BUFFER else 0
