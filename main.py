import threading
import signal
import sys
from core.tray import run_tray
from core.capture import run_capture
from core.ocr import run_ocr
from api.payload import build_payload
from ui.popup import show_popup
from config.settings import (
    missing_api_keys,
    is_onboarding_complete,
    is_sprint_mode,
    complete_onboarding,
)
from storage.sprint import log_sprint_capture


# ── Graceful shutdown ─────────────────────────────────────────────────────────

def handle_exit(sig, frame):
    print("\n[Context Engine] Shutting down... bye.")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_exit)   # Ctrl+C
signal.signal(signal.SIGTERM, handle_exit)  # kill signal


# ── Hotkey trigger ────────────────────────────────────────────────────────────

def on_trigger():
    print("[Main] Hotkey fired — starting capture...")

    capture = run_capture()
    ocr = run_ocr(capture["screenshot"]["path"])

    if is_sprint_mode():
        log_sprint_capture(
            git_diff=capture["git_diff"].get("diff", ""),
            ocr_text=ocr.get("text", ""),
            raw_thought="",
            timestamp=capture["screenshot"]["timestamp"],
        )
        print("[Main] Sprint Mode — capture logged silently.")
        return

    def on_submit(raw_thought):
        print(f"[Main] Raw thought received: '{raw_thought}'")
        payload = build_payload(
            raw_thought=raw_thought,
            ocr_result=ocr,
            capture_result=capture,
        )
        print("[Main] Payload built — ready for AI generation.")
        print(f"[Main] Payload preview: {payload['user_message'][:200]}")

    def on_dismiss():
        print("[Main] Capture dismissed.")

    show_popup(on_submit=on_submit, on_dismiss=on_dismiss)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    missing = missing_api_keys()
    if missing:
        print(f"[Warning] Missing API keys: {', '.join(missing)}")

    if not is_onboarding_complete():
        print("[Context Engine] First launch — set your Project Narrative via tray → Settings.")
        complete_onboarding()

    print("[Context Engine] Running — press Ctrl+Shift+P to trigger.")
    print("[Context Engine] Press Ctrl+C to quit.\n")

    try:
        run_tray(trigger_callback=on_trigger)
    except KeyboardInterrupt:
        handle_exit(None, None)