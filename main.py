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
        print("[Main] Hotkey ignored — already processing a capture.")
        return
    
    _is_processing = True
    print("[Main] Hotkey fired — capturing code instantly...")
    
    try:
        # 0.5s buffer to allow hotkey release/OS graphics to clear
        capture = run_capture(delay=0.5)
        ocr = run_ocr(capture["screenshot"]["path"])

        if is_sprint_mode():
            log_sprint_capture(
                git_diff=capture["git_diff"].get("diff", ""),
                ocr_text=ocr.get("text", ""),
                raw_thought="",
                timestamp=capture["screenshot"]["timestamp"],
            )
            print("[Main] Sprint Mode — capture logged silently.")
            _is_processing = False
            return

        # V3 Workflow: Capture context and open dashboard
        print("[Main] Context captured — opening dashboard for refinement...")
        
        payload = build_payload(
            raw_thought="", # No popup, user adds thought in web chat
            ocr_result=ocr,
            capture_result=capture,
        )

        # force Groq until Gemini key is added
        payload["use_vision_fallback"] = False
        payload["screenshot_b64"] = None

        import asyncio
        from ai.generator import generate_posts

        def generate_and_save():
            try:
                print("[Main] Generating initial post variations...")
                variations = asyncio.run(generate_posts(payload))
                
                # Save to CURRENT_DRAFT for Phase 2
                draft_data = {
                    "payload": payload,
                    "variations": variations,
                    "timestamp": payload.get("timestamp", ""),
                    "status": "ready"
                }
                with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
                    json.dump(draft_data, f, indent=4)
                
                print(f"[Main] Variations ready — stored in {CURRENT_DRAFT.name}")
                
            except Exception as e:
                print(f"[Main] Error in generation: {e}")
            finally:
                global _is_processing
                _is_processing = False

        threading.Thread(target=generate_and_save, daemon=True).start()
        
        # Open the dashboard
        webbrowser.open("http://127.0.0.1:8000")
    
    except Exception as e:
        print(f"[Main] Error during capture: {e}")
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