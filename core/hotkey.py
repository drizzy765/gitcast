from pynput import keyboard

_listener = None

def start_hotkey_listener(callback):
    global _listener
    def on_activate():
        callback()

    _listener = keyboard.GlobalHotKeys({
        '<ctrl>+<shift>+p': on_activate
    })
    _listener.start()
    return _listener

def stop_hotkey_listener():
    global _listener
    if _listener:
        _listener.stop()
        _listener = None
        print("[Hotkey] Listener stopped.")