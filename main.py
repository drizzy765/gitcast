from core.tray import run_tray


def on_trigger():
    print("[Context Engine] Hotkey fired — capture will start here")


if __name__ == "__main__":
    print("[Context Engine] Starting... Press Ctrl+Shift+P to trigger.")
    run_tray(trigger_callback=on_trigger)