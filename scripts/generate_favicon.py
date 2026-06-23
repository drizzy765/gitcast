import os
from PIL import Image, ImageDraw, ImageFont

def generate_favicon():
    # Target directory
    assets_dir = "/mnt/c/Users/USER/Documents/context-engine/assets"
    os.makedirs(assets_dir, exist_ok=True)

    sizes = [16, 32, 64]
    images = {}

    # Define color scheme
    bg_color = "#0a0a0a"
    text_color = "#00ff88"

    # Candidate fonts
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    ]
    
    font_path = None
    for path in font_paths:
        if os.path.exists(path):
            font_path = path
            break

    print(f"Using font path: {font_path}")

    for size in sizes:
        # Create image
        img = Image.new("RGBA", (size, size), bg_color)
        draw = ImageDraw.Draw(img)

        # Load font
        font = None
        if font_path:
            # Scale font size based on image size
            font_size = int(size * 0.55)
            # Ensure font size is at least 8px
            font_size = max(font_size, 8)
            try:
                font = ImageFont.truetype(font_path, font_size)
            except Exception as e:
                print(f"Failed to load TrueType font for size {size}: {e}")
        
        if font is None:
            font = ImageFont.load_default()

        # Center text
        text = "GC"
        
        # Calculate text position and draw
        try:
            # Modern Pillow support for anchor="mm"
            # Using center coordinates
            draw.text((size / 2, size / 2), text, fill=text_color, font=font, anchor="mm")
        except Exception:
            # Fallback for older Pillow or default font where anchor might fail
            try:
                # font.getbbox returns (left, top, right, bottom)
                bbox = font.getbbox(text)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
            except AttributeError:
                # Older Pillow versions
                w, h = draw.textsize(text, font=font)
            
            x = (size - w) / 2
            y = (size - h) / 2
            draw.text((x, y), text, fill=text_color, font=font)

        # Save individual PNG
        png_path = os.path.join(assets_dir, f"favicon-{size}x{size}.png")
        img.save(png_path, "PNG")
        print(f"Saved PNG to {png_path}")
        images[size] = img

    # Save favicon.ico combining all sizes from the 64x64 base image
    ico_path = os.path.join(assets_dir, "favicon.ico")
    images[64].save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (64, 64)])
    print(f"Saved ICO to {ico_path}")

if __name__ == "__main__":
    generate_favicon()
