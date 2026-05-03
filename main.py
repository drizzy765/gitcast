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
    is_onboarding_complete,
    is_sprint_mode,
    complete_onboarding,
    CURRENT_DRAFT,
)
from storage.sprint import log_sprint_capture
from storage.cleanup import run_cleanup
from storage.engagement import run_engagement_worker


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
    missing = missing_api_keys()
    if missing:
        print(f"[Warning] Missing API keys: {', '.join(missing)}")

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
    tray_thread = threading.Thread(
        target=run_tray, 
        kwargs={"trigger_callback": on_trigger}, 
        daemon=True
    )
    tray_thread.start()

    try:
        # Keep the main thread alive and responsive to SIGINT
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        handle_exit(None, None)