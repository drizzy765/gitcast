from core.tray import run_tray
from config.settings import missing_api_keys, is_onboarding_complete


def on_trigger():
    print("[Context Engine] Hotkey fired — capture will start here")


if __name__ == "__main__":
    missing = missing_api_keys()
    if missing:
        print(f"[Warning] Missing API keys: {', '.join(missing)}")
        print("Add them to your .env file before publishing will work.")

    if not is_onboarding_complete():
        print("[Context Engine] First launch — Project Narrative not set.")
        print("Set it via the tray menu: Settings → Project Narrative")

    print("[Context Engine] Starting... Press Ctrl+Shift+P to trigger.")
    run_tray(trigger_callback=on_trigger)