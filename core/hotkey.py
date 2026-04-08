from pynput import keyboard

def start_hotkey_listener(callback):
    def on_activate():
        callback()

    listener = keyboard.GlobalHotKeys({
        '<ctrl>+<shift>+p': on_activate
    })
    listener.start()
    return listener