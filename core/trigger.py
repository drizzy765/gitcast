<<<<<<< HEAD
import threading
from core.capture import run_capture
from core.ocr import run_ocr
from api.payload import build_payload
from ui.popup import show_popup
from config.settings import is_sprint_mode, get_project_narrative, set_project_narrative
from storage.sprint import log_sprint_capture
from ai.generator import generate_posts
from ui.review import show_review
from publisher.twitter import publish_post
from storage.logger import log_post
import asyncio

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


def _generate_and_open(raw_thought, capture, ocr):
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

    narrative = get_project_narrative()

    if narrative:
        # silent mode — no popup
        # use narrative as the raw thought
        raw_thought = narrative
        print("[Trigger] using project narrative — skipping popup")
        _generate_and_open(raw_thought, capture, ocr)

    else:
        # first time or no narrative — show popup once
        # but frame it as "what are you building?"
        # not "what was the struggle or win?"
        print("[Trigger] no narrative set — showing setup popup")

        def on_submit(thought):
            from config.settings import set_project_narrative
            # save as project narrative for future
            set_project_narrative(thought)
            print(f"[Trigger] narrative saved: '{thought}'")
            _generate_and_open(thought, capture, ocr)

        def on_dismiss():
            print("[Trigger] popup dismissed")

        # update popup text to ask for narrative
        show_popup(
            on_submit=on_submit,
            on_dismiss=on_dismiss,
            prompt_text="What are you building? (saved for future captures)"
        )
=======
import threading
from core.capture import run_capture
from core.ocr import run_ocr
from api.payload import build_payload
from ui.popup import show_popup
from config.settings import is_sprint_mode, get_project_narrative, set_project_narrative
from storage.sprint import log_sprint_capture
from ai.generator import generate_posts
from ui.review import show_review
from publisher.twitter import publish_post
from storage.logger import log_post
import asyncio

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
    payload = build_payload(
        raw_thought=raw_thought,
        ocr_result=ocr,
        capture_result=capture,
    )
    payload["use_vision_fallback"] = False
    payload["screenshot_b64"] = None

    # inject project context into payload
    payload["project_name"] = project_ctx["project_name"]
    payload["readme_content"] = project_ctx["readme_content"]
    payload["tech_stack"] = project_ctx["tech_stack"]
    payload["project_type"] = project_ctx["project_type"]
    payload["main_language"] = project_ctx["main_language"]

    # build enriched user message
    if project_ctx["readme_content"]:
        payload["user_message"] = (
            payload.get("user_message", "") +
            f"\n\n## Project: "
            f"{project_ctx['project_name']}\n"
            f"## Tech stack: "
            f"{project_ctx['tech_stack']}\n"
            f"## README context:\n"
            f"{project_ctx['readme_content'][:1500]}"
        )

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

    # read project context FIRST before capture
    from core.project_reader import (
        read_project_context, detect_gitcast_window)
    from core.capture import detect_working_directory

    working_dir = detect_working_directory()
    project_ctx = read_project_context(working_dir)

    if project_ctx["readme_content"]:
        print(f"[Trigger] README found for: "
              f"{project_ctx['project_name']}")
    if project_ctx["tech_stack"]:
        print(f"[Trigger] Stack: "
              f"{project_ctx['tech_stack'][:60]}")

    # run capture
    print("[Gitcast] Hotkey fired — starting capture...")
    capture = run_capture()
    print("[Trigger] capture complete")
    ocr = run_ocr(capture["screenshot"]["path"])
    print("[Trigger] OCR complete")

    # detect if user captured Gitcast dashboard
    ocr_text = ocr.get("text", "") or \
               ocr.get("raw_text", "")
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

        # show tray notification
        try:
            from plyer import notification
            notification.notify(
                title="Gitcast",
                message="Switch to your code editor "
                        "then press Ctrl+Shift+P again",
                timeout=5,
            )
        except Exception:
            pass

        # clear OCR text — don't send dashboard content to AI
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
        # but frame it as "what are you building?"
        # not "what was the struggle or win?"
        print("[Trigger] no narrative set — showing setup popup")

        def on_submit(thought):
            from config.settings import set_project_narrative
            # save as project narrative for future
            set_project_narrative(thought)
            print(f"[Trigger] narrative saved: '{thought}'")
            _generate_and_open(thought, capture, ocr, project_ctx)

        def on_dismiss():
            print("[Trigger] popup dismissed")

        # update popup text to ask for narrative
        show_popup(
            on_submit=on_submit,
            on_dismiss=on_dismiss,
            prompt_text="What are you building? (saved for future captures)"
        )

>>>>>>> 1305f09 ( docs: update README with detailed features, CLI reference, and architecture flow)
