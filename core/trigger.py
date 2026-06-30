import threading
from core.capture import run_capture
from core.ocr import run_ocr
from api.payload import build_payload
from ui.popup import show_popup
from config.settings import is_sprint_mode
from storage.sprint import log_sprint_capture
from ai.generator import generate_posts
from ui.review import show_review
from publisher.twitter import publish_post
from storage.logger import log_post
import asyncio
import webbrowser

_browser_opened = False


def on_trigger():
    """
    Called every time the hotkey fires.
    Full capture → generate → review flow.
    """
    print("[Trigger] on_trigger fired successfully")
    print("[Gitcast] Hotkey fired — starting capture...")

    capture = run_capture()
    print("[Trigger] capture complete")
    ocr = run_ocr(capture["screenshot"]["path"])
    print("[Trigger] OCR complete")

    if is_sprint_mode():
        log_sprint_capture(
            git_diff=capture["git_diff"].get("diff", ""),
            ocr_text=ocr.get("text", ""),
            raw_thought="",
            timestamp=capture["screenshot"]["timestamp"],
        )
        print("[Gitcast] Sprint Mode — capture logged silently.")
        return

    def on_submit(raw_thought):
        print("[Trigger] raw thought received")
        print(f"[Gitcast] Raw thought: '{raw_thought}'")
        payload = build_payload(
            raw_thought=raw_thought,
            ocr_result=ocr,
            capture_result=capture,
        )
        payload["use_vision_fallback"] = False
        payload["screenshot_b64"] = None

        def generate_and_show():
            try:
                print('[Trigger] calling generate_posts...')
                print("[Trigger] generating posts...")
                variations = asyncio.run(generate_posts(payload))
                print(f'[Trigger] got {len(variations)} variations')
                print(f'[Trigger] keys: {list(variations.keys())}')
                for k, v in variations.items():
                    print(f'[Trigger] {k}: {v[:50]}...')

                global _browser_opened
                if not _browser_opened:
                    print("[Trigger] opening review window")
                    webbrowser.open("http://localhost:8000")
                    _browser_opened = True
                else:
                    print("> [OK] Posts generated. Refresh or check your active dashboard tab at http://localhost:8000")

                def on_publish(post_text, format_key,
                               screenshot_path):
                    print(f"[Gitcast] Publishing: {format_key}")
                    result = publish_post(
                        post_text, screenshot_path)
                    if result.get("success"):
                        if result.get("fallback"):
                            print("[Gitcast] Copied to clipboard")
                        else:
                            print(f"[Gitcast] Published: "
                                  f"{result.get('tweet_url')}")
                        log_post(
                            post_text=post_text,
                            format_key=format_key,
                            screenshot_path=screenshot_path,
                            tweet_url=result.get(
                                "tweet_url", ""),
                            tweet_id=result.get(
                                "tweet_id", ""),
                            fallback=result.get(
                                "fallback", False),
                        )
                    else:
                        print(f"[Gitcast] Error: "
                              f"{result.get('error')}")

                def on_close():
                    print("[Gitcast] Review closed.")

                show_review(
                    payload=payload,
                    variations=variations,
                    on_publish=on_publish,
                    on_close=on_close,
                )
            except Exception as e:
                print(f'[Trigger] generation error: {e}')
                import traceback
                traceback.print_exc()

        threading.Thread(
            target=generate_and_show,
            daemon=True
        ).start()

    def on_dismiss():
        print("[Gitcast] Capture dismissed.")

    print("[Trigger] popup showing")
    show_popup(
        on_submit=on_submit,
        on_dismiss=on_dismiss
    )
