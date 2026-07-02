from pynput import keyboard
import time

_listener = None
_last_trigger_time = 0
COOLDOWN_SECONDS = 3

def start_hotkey_listener(callback):
    global _listener
    def on_activate():
        global _last_trigger_time
        now = time.time()
        if now - _last_trigger_time < COOLDOWN_SECONDS:
            print("[Hotkey] cooldown — ignoring rapid repeat")
            return
        _last_trigger_time = now
        callback()

    _listener = keyboard.GlobalHotKeys({
        '<ctrl>+<shift>+p': on_activate,
        '<ctrl>+<alt>+s': on_activate
    })
    _listener.start()
    return _listener

def stop_hotkey_listener():
    global _listener
    if _listener:
        _listener.stop()
        _listener = None
        print("[Hotkey] Listener stopped.")