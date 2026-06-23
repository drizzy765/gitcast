import pystray
import os
from PIL import Image, ImageDraw
from pystray import MenuItem as item
import webbrowser
from .hotkey import start_hotkey_listener, stop_hotkey_listener

_icon = None

def create_image():
    # Generate a simple icon
    width = 64
    height = 64
    color1 = (0, 128, 255)
    color2 = (255, 255, 255)
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 4, height // 4, width * 3 // 4, height * 3 // 4),
        fill=color2
    )
    return image

def run_tray(trigger_callback):
    global _icon
    # Start the hotkey listener
    start_hotkey_listener(trigger_callback)

    def on_quit(icon, item):
        stop_tray()
        os._exit(0)

    def trigger_action(icon, item):
        trigger_callback()

    def open_dashboard(icon, item):
        webbrowser.open("http://127.0.0.1:8000")

    image = create_image()
    menu = pystray.Menu(
        item('Dashboard', open_dashboard),
        item('Trigger Capture (Ctrl+Alt+S)', trigger_action),
        item('Quit', on_quit)
    )

    _icon = pystray.Icon("gitcast", image, "Gitcast", menu)
    _icon.run()

def stop_tray():
    global _icon
    stop_hotkey_listener()
    if _icon:
        _icon.stop()
        print("[Tray] Icon stopped.")