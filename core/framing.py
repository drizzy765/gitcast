import os
from PIL import Image, ImageDraw, ImageFilter, ImageOps

def add_programming_frame(image_path: str) -> str:
    """
    Wraps a screenshot in a macOS-style window frame with traffic lights
    and a drop shadow. Saves the result as a new file.
    """
    if not os.path.exists(image_path):
        return image_path

    # Load original image
    img = Image.open(image_path).convert("RGBA")
    
    # Constants for the frame
    CORNER_RADIUS = 12
    HEADER_HEIGHT = 36
    PADDING = 60 # Outer padding for shadow and background
    BG_COLOR = (30, 30, 30, 255) # Dark grey for the "window"
    SHADOW_COLOR = (0, 0, 0, 100)
    
    # Traffic light colors
    RED = (255, 95, 87, 255)
    YELLOW = (255, 189, 46, 255)
    GREEN = (40, 201, 64, 255)
    LIGHT_SIZE = 12
    LIGHT_SPACING = 20
    LIGHT_MARGIN_LEFT = 16
    LIGHT_MARGIN_TOP = (HEADER_HEIGHT - LIGHT_SIZE) // 2

    # 1. Create the window content (Header + Screenshot)
    win_width = img.width
    win_height = img.height + HEADER_HEIGHT
    
    # Create window background with rounded corners
    window = Image.new("RGBA", (win_width, win_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(window)
    
    # Draw rounded rectangle for the whole window
    draw.rounded_rectangle(
        [0, 0, win_width, win_height],
        radius=CORNER_RADIUS,
        fill=BG_COLOR
    )
    
    # Paste the original screenshot below the header
    window.paste(img, (0, HEADER_HEIGHT), img if img.mode == 'RGBA' else None)
    
    # Draw traffic lights
    for i, color in enumerate([RED, YELLOW, GREEN]):
        x = LIGHT_MARGIN_LEFT + (i * LIGHT_SPACING)
        y = LIGHT_MARGIN_TOP
        draw.ellipse([x, y, x + LIGHT_SIZE, y + LIGHT_SIZE], fill=color)

    # 2. Add Drop Shadow
    # Create a canvas larger than the window to hold the shadow
    canvas_width = win_width + (PADDING * 2)
    canvas_height = win_height + (PADDING * 2)
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    
    # Create shadow mask
    shadow_mask = Image.new("L", (win_width, win_height), 0)
    shadow_draw = ImageDraw.Draw(shadow_mask)
    shadow_draw.rounded_rectangle([0, 0, win_width, win_height], radius=CORNER_RADIUS, fill=180)
    
    # Blur the shadow
    shadow = Image.new("RGBA", (win_width, win_height), (0, 0, 0, 150))
    shadow.putalpha(shadow_mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=25))
    
    # Offset shadow slightly
    canvas.paste(shadow, (PADDING + 5, PADDING + 10))
    
    # Paste the window on top
    canvas.paste(window, (PADDING, PADDING), window)

    # Save framed image
    base, ext = os.path.splitext(image_path)
    framed_path = f"{base}_framed.png"
    canvas.save(framed_path)
    
    return framed_path

if __name__ == "__main__":
    # Test with a dummy image if exists or just print
    print("Framing module ready. Use add_programming_frame(path) to test.")
