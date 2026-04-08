import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem as item
from .hotkey import start_hotkey_listener

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
    # Start the hotkey listener
    start_hotkey_listener(trigger_callback)

    def quit_action(icon, item):
        icon.stop()

    def trigger_action(icon, item):
        trigger_callback()

    image = create_image()
    menu = pystray.Menu(
        item('Trigger Capture (Ctrl+Shift+P)', trigger_action),
        item('Quit', quit_action)
    )

    icon = pystray.Icon("context_engine", image, "Context Engine", menu)
    icon.run()