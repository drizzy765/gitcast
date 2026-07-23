import threading
import asyncio
from core.capture import run_capture, detect_working_directory
from core.ocr import run_ocr
from core.project_reader import read_project_context, detect_gitcast_window
from api.payload import build_payload
from ui.popup import show_popup
from config.settings import is_sprint_mode, get_project_narrative, set_project_narrative
from storage.sprint import log_sprint_capture
from ai.generator import generate_posts
from ui.review import show_review
from publisher.twitter import publish_post
from storage.logger import log_post

_capture_lock = threading.Event()
_capture_lock.set()  # start as "not capturing"


def on_trigger():
    # prevent concurrent captures
    if not _capture_lock.is_set():
        print("[Trigger] capture already in progress — ignoring")
        return

    _capture_lock.clear()  # mark as capturing
    try:
        _run_trigger()
    finally:
        _capture_lock.set()  # release lock


def _show_tray_notification(title, message):
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="Gitcast",
            timeout=4,
        )
    except Exception:
        print(f"[Trigger] {title}: {message}")


def _generate_and_open(raw_thought, capture, ocr, project_ctx):
    # Step 5: build_payload()
    payload = build_payload(
        raw_thought=raw_thought,
        ocr_result=ocr,
        capture_result=capture,
        project_ctx=project_ctx,
    )
    payload["use_vision_fallback"] = False
    payload["screenshot_b64"] = None

    # Step 6: generate_posts()
    def generate_and_show():
        try:
            print('[Trigger] calling generate_posts...')
            print("[Trigger] generating posts...")
            variations = asyncio.run(generate_posts(payload))
            print(f'[Trigger] got {len(variations)} variations')
            print(f'[Trigger] keys: {list(variations.keys())}')
            for k, v in variations.items():
                print(f'[Trigger] {k}: {v[:50]}...')

            def on_publish(post_text, format_key, screenshot_path):
                print(f"[Gitcast] Publishing: {format_key}")
                result = publish_post(post_text, screenshot_path)
                if result.get("success"):
                    if result.get("fallback"):
                        print("[Gitcast] Copied to clipboard")
                    else:
                        print(f"[Gitcast] Published: {result.get('tweet_url')}")
                    log_post(
                        post_text=post_text,
                        format_key=format_key,
                        screenshot_path=screenshot_path,
                        tweet_url=result.get("tweet_url", ""),
                        tweet_id=result.get("tweet_id", ""),
                        fallback=result.get("fallback", False),
                    )
                else:
                    print(f"[Gitcast] Error: {result.get('error')}")

            def on_close():
                print("[Gitcast] Review closed.")

            show_review(
                payload=payload,
                variations=variations,
                on_publish=on_publish,
                on_close=on_close,
            )

            _show_tray_notification(
                "Gitcast",
                "Post ready — check dashboard"
            )

        except Exception as e:
            print(f'[Trigger] generation error: {e}')
            import traceback
            traceback.print_exc()

    threading.Thread(
        target=generate_and_show,
        daemon=True
    ).start()


def _run_trigger():
    """The actual trigger logic — moved from on_trigger."""
    print("[Trigger] on_trigger fired successfully")

    # Step 1: read_project_context()
    working_dir = detect_working_directory()
    project_ctx = read_project_context(working_dir)

    if project_ctx.get("readme_content"):
        print(f"[Trigger] README found for: {project_ctx['project_name']}")
    if project_ctx.get("tech_stack"):
        print(f"[Trigger] Stack: {project_ctx['tech_stack'][:60]}")

    # Step 2: run_capture()
    print("[Gitcast] Hotkey fired — starting capture...")
    capture = run_capture()
    print("[Trigger] capture complete")

    # Step 3: run_ocr()          ← must finish first
    ocr = run_ocr(capture["screenshot"]["path"])
    print("[Trigger] OCR complete")

    # Step 4: detect_gitcast_window()
    ocr_text = ocr.get("text", "") or ocr.get("raw_text", "")
    if detect_gitcast_window(ocr_text):
        print("""
  > [!!] You captured the Gitcast dashboard.
  >
  > For best results:
  >   1. Switch to your code editor (VS Code,
  >      PyCharm, terminal with your code)
  >   2. Press Ctrl+Shift+P again
  >
  > The 5-second countdown gives you time to switch.
  > Gitcast will still generate using your README
  > and project narrative as context.
        """)

        _show_tray_notification(
            "Gitcast",
            "Switch to your code editor then press Ctrl+Shift+P again"
        )

        ocr["text"] = ""
        ocr["raw_text"] = ""
        ocr["reliable"] = False

    if is_sprint_mode():
        log_sprint_capture(
            git_diff=capture["git_diff"].get("diff", ""),
            ocr_text=ocr.get("text", ""),
            raw_thought="",
            timestamp=capture["screenshot"]["timestamp"],
        )
        print("[Gitcast] Sprint Mode — capture logged silently.")
        return

    narrative = get_project_narrative()

    if narrative:
        # silent mode — no popup
        # use narrative as the raw thought
        raw_thought = narrative
        print("[Trigger] using project narrative — skipping popup")
        _generate_and_open(raw_thought, capture, ocr, project_ctx)

    else:
        # first time or no narrative — show popup once
        print("[Trigger] no narrative set — showing setup popup")

        def on_submit(thought):
            set_project_narrative(thought)
            print(f"[Trigger] narrative saved: '{thought}'")
            _generate_and_open(thought, capture, ocr, project_ctx)

        def on_dismiss():
            print("[Trigger] popup dismissed")

        show_popup(
            on_submit=on_submit,
            on_dismiss=on_dismiss,
            prompt_text="What are you building? (saved for future captures)"
        )
