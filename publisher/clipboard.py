import webbrowser


def copy_to_clipboard(post_text: str) -> dict:
    """Copy post text to the system clipboard using tkinter."""
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.clipboard_clear()
        root.clipboard_append(post_text)
        root.update()  # required for clipboard to persist after destroy
        root.destroy()
        print("[Publisher] Text copied to clipboard.")
        return {"success": True, "method": "clipboard"}
    except Exception as e:
        print(f"[Publisher] Clipboard copy failed: {e}")
        return {"success": False, "error": str(e)}


def open_x_compose(post_text: str) -> dict:
    """Copy text to clipboard then open X compose page in the default browser."""
    try:
        clip_result = copy_to_clipboard(post_text)
        if not clip_result["success"]:
            return clip_result

        compose_url = "https://twitter.com/compose/tweet"
        webbrowser.open(compose_url)
        print(f"[Publisher] Opened {compose_url} — paste your post from clipboard.")
        return {"success": True, "method": "clipboard"}
    except Exception as e:
        print(f"[Publisher] Failed to open X compose: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    sample = "🚀 Just shipped a new feature! Building in public with Context Engine. #buildinpublic #devtools"
    print("[Publisher] Testing open_x_compose...")
    result = open_x_compose(sample)
    print(f"[Publisher] Result: {result}")
