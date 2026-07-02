import tkinter as tk
from tkinter import font as tkfont
import threading


# ── Constants ─────────────────────────────────────────────────────────────────

POPUP_WIDTH = 520
POPUP_HEIGHT = 120
BG_COLOR = "#1a1a1a"
BORDER_COLOR = "#333333"
TEXT_COLOR = "#f0f0f0"
PLACEHOLDER_COLOR = "#555555"
ACCENT_COLOR = "#6366f1"  # indigo — matches tray icon
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 13


# ── Popup window ──────────────────────────────────────────────────────────────

class CapturePopup:
    def __init__(self, on_submit, on_dismiss):
        """
        Args:
            on_submit:  Callback called with the user's raw thought string.
            on_dismiss: Callback called when the user hits Esc or closes.
        """
        self.on_submit = on_submit
        self.on_dismiss = on_dismiss
        self.result = None
        self.root = None

    def show(self):
        """Build and display the popup. Blocks until submitted or dismissed."""
        self.root = tk.Tk()
        self.root.withdraw()  # hide while building to prevent flicker

        self._configure_window()
        self._build_ui()
        self._center_on_screen()
        self._bind_keys()

        self.root.deiconify()  # show fully built window
        self.root.focus_force()
        self.entry.focus_set()

        self.root.mainloop()

    def _configure_window(self):
        self.root.title("")
        self.root.configure(bg=BG_COLOR)
        self.root.overrideredirect(True)   # removes title bar and border
        self.root.attributes("-topmost", True)  # float above all windows
        self.root.resizable(False, False)

        # draw a 1px border using a frame
        self.root.configure(highlightbackground=BORDER_COLOR, highlightthickness=1)

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg=BG_COLOR, padx=20, pady=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # label
        label_font = tkfont.Font(family=FONT_FAMILY, size=10)
        label = tk.Label(
            main_frame,
            text="What was the struggle or win?",
            bg=BG_COLOR,
            fg=PLACEHOLDER_COLOR,
            font=label_font,
            anchor="w",
        )
        label.pack(fill=tk.X, pady=(0, 8))

        # accent line under label
        accent_line = tk.Frame(main_frame, bg=ACCENT_COLOR, height=1)
        accent_line.pack(fill=tk.X, pady=(0, 10))

        # text input
        entry_font = tkfont.Font(family=FONT_FAMILY, size=FONT_SIZE)
        self.entry = tk.Entry(
            main_frame,
            font=entry_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            insertbackground=ACCENT_COLOR,  # cursor color
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
        )
        self.entry.pack(fill=tk.X)

        # hint text at bottom
        hint_font = tkfont.Font(family=FONT_FAMILY, size=9)
        hint = tk.Label(
            main_frame,
            text="Enter to capture  ·  Esc to cancel",
            bg=BG_COLOR,
            fg=PLACEHOLDER_COLOR,
            font=hint_font,
            anchor="e",
        )
        hint.pack(fill=tk.X, pady=(10, 0))

    def _center_on_screen(self):
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - POPUP_WIDTH) // 2
        y = int(screen_h * 0.38)  # slightly above center — feels more natural
        self.root.geometry(f"{POPUP_WIDTH}x{POPUP_HEIGHT}+{x}+{y}")

    def _bind_keys(self):
        self.root.bind("<Return>", self._handle_submit)
        self.root.bind("<Escape>", self._handle_dismiss)
        self.root.bind("<FocusOut>", self._handle_focus_out)
        self.root.protocol("WM_DELETE_WINDOW", self._handle_dismiss)

    def _handle_submit(self, event=None):
        text = self.entry.get().strip()
        if not text:
            # shake the entry to signal empty input
            self._shake()
            return
        self.result = text
        self.root.destroy()
        self.on_submit(text)

    def _handle_dismiss(self, event=None):
        self.root.destroy()
        self.on_dismiss()

    def _handle_focus_out(self, event=None):
        """Dismiss if user clicks away from the popup."""
        self.root.destroy()
        self.on_dismiss()

    def _shake(self):
        """Briefly shakes the window to signal empty input."""
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        for delta in [6, -6, 4, -4, 2, -2, 0]:
            self.root.geometry(f"{POPUP_WIDTH}x{POPUP_HEIGHT}+{x + delta}+{y}")
            self.root.update()
            self.root.after(18)


# ── Public interface ──────────────────────────────────────────────────────────

def show_popup(on_submit, on_dismiss):
    """
    Shows the capture popup in a new thread so it doesn't block
    the hotkey listener or the tray process.
    """
    def run():
        try:
            popup = CapturePopup(on_submit=on_submit, on_dismiss=on_dismiss)
            popup.show()
        except Exception as e:
            print(f"[Gitcast] Popup display error: {e}")
            on_dismiss()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread
