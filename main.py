import threading
import signal
import sys
import os
import time
import webbrowser
import json
from core.tray import run_tray, stop_tray
from api.server import start_server
from core.capture import run_capture
from core.ocr import run_ocr
from api.payload import build_payload
from config.settings import (
    missing_api_keys,
    ai_provider_key_status,
    is_onboarding_complete,
    is_sprint_mode,
    complete_onboarding,
    CURRENT_DRAFT,
)
from storage.sprint import log_sprint_capture
from storage.cleanup import run_cleanup
from storage.engagement import run_engagement_worker
from api.analytics import track
from api.monitoring import capture_error, init_sentry


# ── Graceful shutdown ─────────────────────────────────────────────────────────

def handle_exit(sig, frame):
    print("\n[Context Engine] Shutting down... bye.")
    stop_tray()
    os._exit(0)

signal.signal(signal.SIGINT, handle_exit)   # Ctrl+C
signal.signal(signal.SIGTERM, handle_exit)  # kill signal


# ── Hotkey trigger ────────────────────────────────────────────────────────────

_is_processing = False

def on_trigger():
    global _is_processing
    if _is_processing:
        return
    
    _is_processing = True
    print("[Main] Hotkey fired — starting interactive session...")
    
    try:
        from core.screenshot_session import ScreenshotSession
        session = ScreenshotSession()
        session.run()
    except Exception as e:
        print(f"[Main] Error during session: {e}")
    finally:
        _is_processing = False


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_sentry()
    track("app_started", {"version": "3.0"})
    missing = missing_api_keys()
    if missing:
        print(f"[Warning] Missing API keys: {', '.join(missing)}")

    if not any(ai_provider_key_status().values()):
        print(
            "\n"
            "> [!!] NO API KEYS DETECTED\n"
            ">\n"
            "> context engine needs at least one AI provider key.\n"
            "> all keys are free to obtain:\n"
            ">\n"
            ">   GROQ (recommended first key)\n"
            ">   -> console.groq.com\n"
            ">   -> free tier: 12k tokens/minute\n"
            ">   -> best for: quick posts, linkedin\n"
            ">\n"
            ">   DEEPSEEK (recommended second key)\n"
            ">   -> platform.deepseek.com\n"
            ">   -> free tier: $5 credit on signup\n"
            ">   -> best for: technical posts, PR descriptions\n"
            ">\n"
            ">   GEMINI (required for vision fallback)\n"
            ">   -> aistudio.google.com\n"
            ">   -> free tier: 1M tokens/day\n"
            ">   -> best for: screenshots with low OCR confidence\n"
            ">\n"
            "> add keys to your .env file or via the dashboard:\n"
            "> http://127.0.0.1:8000/app -> settings -> api_keys\n"
            ">\n"
            "> setup guide: github.com/YOUR_USERNAME/context-engine\n"
        )

    if not is_onboarding_complete():
        print("[Context Engine] First launch — set your Project Narrative via tray → Settings.")
        complete_onboarding()

    print("[Context Engine] Running — press Ctrl+Alt+S to trigger (Instant).")
    print("[Context Engine] Press Ctrl+C to quit.\n")

    # Run maintenance tasks
    run_cleanup()
    run_engagement_worker()

    # Start API server in a daemon thread
    api_thread = threading.Thread(target=start_server, daemon=True)
    api_thread.start()

    # Start tray in a daemon thread so it doesn't block signal handling in main thread
    def run_tray_guarded():
        try:
            run_tray(trigger_callback=on_trigger)
        except Exception as e:
            capture_error(e, {"module": "tray"})

    tray_thread = threading.Thread(
        target=run_tray_guarded,
        daemon=True
    )
    tray_thread.start()

    try:
        # Keep the main thread alive and responsive to SIGINT
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        handle_exit(None, None)
