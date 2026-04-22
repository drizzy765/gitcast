import threading
from core.tray import run_tray
from core.capture import run_capture
from core.ocr import run_ocr
from api.payload import build_payload
from ui.popup import show_popup
from config.settings import missing_api_keys, is_onboarding_complete, is_sprint_mode
from storage.sprint import log_sprint_capture


def on_trigger():
    """Called every time the hotkey fires."""
    print("[Main] Hotkey fired — starting capture...")

    # run capture immediately in background
    capture = run_capture()
    ocr = run_ocr(capture["screenshot"]["path"])

    if is_sprint_mode():
        # Sprint Mode — silent capture, no popup
        log_sprint_capture(
            git_diff=capture["git_diff"].get("diff", ""),
            ocr_text=ocr.get("text", ""),
            raw_thought="",
            timestamp=capture["screenshot"]["timestamp"],
        )
        print("[Main] Sprint Mode — capture logged silently.")
        return

    # normal mode — show popup
    def on_submit(raw_thought):
        print(f"[Main] Raw thought received: '{raw_thought}'")
        payload = build_payload(
            raw_thought=raw_thought,
            ocr_result=ocr,
            capture_result=capture,
        )
        print("[Main] Payload built — ready for AI generation.")
        # ai generation + review UI will be wired here next session
        print(f"[Main] Payload preview: {payload['user_message'][:200]}")

    def on_dismiss():
        print("[Main] Capture dismissed.")

    show_popup(on_submit=on_submit, on_dismiss=on_dismiss)


if __name__ == "__main__":
    missing = missing_api_keys()
    if missing:
        print(f"[Warning] Missing API keys: {', '.join(missing)}")

    if not is_onboarding_complete():
        print("[Context Engine] First launch — set your Project Narrative via tray → Settings.")

    print("[Context Engine] Running — press Ctrl+Shift+P to trigger.")
    run_tray(trigger_callback=on_trigger)