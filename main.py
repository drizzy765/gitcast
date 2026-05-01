import threading
import signal
import sys
import os
import time
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
    print("[Main] Hotkey fired — starting capture...")

    try:
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
            _is_processing = False
            return

        def on_submit(raw_thought):
            print(f"[Main] Raw thought received: '{raw_thought}'")

            payload = build_payload(
                raw_thought=raw_thought,
                ocr_result=ocr,
                capture_result=capture,
            )

            # force Groq until Gemini key is added
            payload["use_vision_fallback"] = False
            payload["screenshot_b64"] = None

            print("[Main] Generating posts...")

            import asyncio
            from ai.generator import generate_posts
            from ui.review import show_review

            def generate_and_show():
                try:
                    variations = asyncio.run(generate_posts(payload))

                    def on_publish(post_text, format_key, screenshot_path):
                        print(f"[Main] Publishing: {format_key}")

                        from publisher.twitter import publish_post
                        from storage.logger import log_post

                        result = publish_post(post_text, screenshot_path)

                        if result.get("success") and not result.get("fallback"):
                            tweet_url = result.get("tweet_url", "")
                            tweet_id = result.get("tweet_id", "")
                            print(f"[Main] Tweet posted — {tweet_url}")
                            log_post(
                                post_text=post_text,
                                format_key=format_key,
                                screenshot_path=screenshot_path,
                                tweet_url=tweet_url,
                                tweet_id=tweet_id,
                                fallback=False,
                            )
                        elif result.get("fallback"):
                            print("[Main] Clipboard fallback was used.")
                            log_post(
                                post_text=post_text,
                                format_key=format_key,
                                screenshot_path=screenshot_path,
                                tweet_url="",
                                tweet_id="",
                                fallback=True,
                            )
                        else:
                            print(f"[Main] Publish failed: {result.get('error', 'unknown error')}")

                    def on_close():
                        global _is_processing
                        print("[Main] Review closed.")
                        _is_processing = False

                    show_review(
                        payload=payload,
                        variations=variations,
                        on_publish=on_publish,
                        on_close=on_close,
                    )
                except Exception as e:
                    global _is_processing
                    print(f"[Main] Error in generation/review: {e}")
                    _is_processing = False

            threading.Thread(target=generate_and_show, daemon=True).start()
        
        # Launch the popup and pass the callback function
        def on_dismiss():
            global _is_processing
            print("[Main] Capture dismissed.")
            _is_processing = False

        show_popup(on_submit=on_submit, on_dismiss=on_dismiss)
    
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

    print("[Context Engine] Running — press Ctrl+Shift+P to trigger.")
    print("[Context Engine] Press Ctrl+C to quit.\n")

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