import tkinter as tk
from tkinter import ttk, font as tkfont, messagebox
import threading
from PIL import Image, ImageTk
from pathlib import Path


# ── Constants ─────────────────────────────────────────────────────────────────

BG_PRIMARY = "#1a1a1a"
BG_SECONDARY = "#242424"
BG_TAB = "#2a2a2a"
BG_TAB_ACTIVE = "#1a1a1a"
BORDER_COLOR = "#333333"
TEXT_PRIMARY = "#f0f0f0"
TEXT_SECONDARY = "#888888"
ACCENT_COLOR = "#6366f1"
SUCCESS_COLOR = "#22c55e"
ERROR_COLOR = "#ef4444"
FONT_FAMILY = "Segoe UI"

TAB_LABELS = {
    "deep_tech": "Deep Tech",
    "struggle": "The Struggle",
    "quick_win": "Quick Win",
    "pr_generator": "PR Description",
}


# ── Review window ─────────────────────────────────────────────────────────────

class ReviewWindow:
    def __init__(self, payload: dict, on_publish, on_close):
        """
        Args:
            payload:    The assembled payload dict from api/payload.py
            on_publish: Callback called with (post_text, format_key, screenshot_path)
            on_close:   Callback called when window is closed without publishing
        """
        self.payload = payload
        self.on_publish = on_publish
        self.on_close = on_close
        self.root = None
        self.variations = {}        # format_key → generated text
        self.text_widgets = {}      # format_key → tk.Text widget
        self.status_var = None
        self.selected_tab = None
        self.screenshot_image = None

    def show(self, variations: dict):
        """
        Build and display the review window.
        Args:
            variations: dict of format_key → generated post text
        """
        self.variations = variations

        self.root = tk.Tk()
        self.root.withdraw()

        self._configure_window()
        self._build_ui()
        self._center_on_screen()
        self._bind_keys()

        self.root.deiconify()
        self.root.focus_force()
        self.root.mainloop()

    def _configure_window(self):
        self.root.title("Context Engine — Review")
        self.root.configure(bg=BG_PRIMARY)
        self.root.attributes("-topmost", True)
        self.root.resizable(True, True)
        self.root.minsize(760, 540)

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=BG_PRIMARY, pady=14, padx=20)
        header.pack(fill=tk.X)

        title_font = tkfont.Font(family=FONT_FAMILY, size=13, weight="bold")
        tk.Label(
            header,
            text="Context Engine",
            bg=BG_PRIMARY,
            fg=TEXT_PRIMARY,
            font=title_font,
        ).pack(side=tk.LEFT)

        subtitle_font = tkfont.Font(family=FONT_FAMILY, size=10)
        tk.Label(
            header,
            text="Select a post to publish",
            bg=BG_PRIMARY,
            fg=TEXT_SECONDARY,
            font=subtitle_font,
        ).pack(side=tk.LEFT, padx=(10, 0), pady=(3, 0))

        # close button
        close_font = tkfont.Font(family=FONT_FAMILY, size=11)
        tk.Button(
            header,
            text="✕",
            bg=BG_PRIMARY,
            fg=TEXT_SECONDARY,
            font=close_font,
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self._handle_close,
        ).pack(side=tk.RIGHT)

        # divider
        tk.Frame(self.root, bg=BORDER_COLOR, height=1).pack(fill=tk.X)

        # ── Main content area ─────────────────────────────────────────────────
        content = tk.Frame(self.root, bg=BG_PRIMARY)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        # left panel — tabs + text editors
        left = tk.Frame(content, bg=BG_PRIMARY)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_tabs(left)

        # right panel — screenshot preview
        right = tk.Frame(content, bg=BG_PRIMARY, width=220)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(16, 0))
        right.pack_propagate(False)

        self._build_preview(right)

        # ── Footer ────────────────────────────────────────────────────────────
        tk.Frame(self.root, bg=BORDER_COLOR, height=1).pack(fill=tk.X)
        self._build_footer()

    def _build_tabs(self, parent):
        # tab bar
        tab_bar = tk.Frame(parent, bg=BG_PRIMARY)
        tab_bar.pack(fill=tk.X, pady=(0, 12))

        self.tab_buttons = {}
        self.tab_frames = {}

        # content area for tab bodies
        self.tab_content = tk.Frame(parent, bg=BG_PRIMARY)
        self.tab_content.pack(fill=tk.BOTH, expand=True)

        first_key = None
        for format_key, label in TAB_LABELS.items():
            if format_key not in self.variations:
                continue

            if first_key is None:
                first_key = format_key

            # tab button
            btn = tk.Button(
                tab_bar,
                text=label,
                bg=BG_TAB,
                fg=TEXT_SECONDARY,
                font=tkfont.Font(family=FONT_FAMILY, size=10),
                relief=tk.FLAT,
                bd=0,
                padx=14,
                pady=6,
                cursor="hand2",
                command=lambda k=format_key: self._switch_tab(k),
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self.tab_buttons[format_key] = btn

            # tab content frame
            frame = tk.Frame(self.tab_content, bg=BG_PRIMARY)
            self.tab_frames[format_key] = frame

            # text editor
            text_font = tkfont.Font(family=FONT_FAMILY, size=12)
            text = tk.Text(
                frame,
                font=text_font,
                bg=BG_SECONDARY,
                fg=TEXT_PRIMARY,
                insertbackground=ACCENT_COLOR,
                relief=tk.FLAT,
                bd=0,
                padx=16,
                pady=14,
                wrap=tk.WORD,
                highlightthickness=1,
                highlightbackground=BORDER_COLOR,
                highlightcolor=ACCENT_COLOR,
            )
            text.pack(fill=tk.BOTH, expand=True)
            text.insert("1.0", self.variations.get(format_key, ""))
            self.text_widgets[format_key] = text

            # char count label
            count_var = tk.StringVar()
            count_label = tk.Label(
                frame,
                textvariable=count_var,
                bg=BG_PRIMARY,
                fg=TEXT_SECONDARY,
                font=tkfont.Font(family=FONT_FAMILY, size=9),
                anchor="e",
            )
            count_label.pack(fill=tk.X, pady=(4, 0))

            # update char count on keypress
            self._update_char_count(text, count_var, format_key)
            text.bind("<KeyRelease>", lambda e, t=text, v=count_var, k=format_key: self._update_char_count(t, v, k))

        # show first tab by default
        if first_key:
            self._switch_tab(first_key)

    def _switch_tab(self, format_key: str):
        self.selected_tab = format_key

        # hide all frames
        for frame in self.tab_frames.values():
            frame.pack_forget()

        # show selected
        self.tab_frames[format_key].pack(fill=tk.BOTH, expand=True)

        # update button styles
        for key, btn in self.tab_buttons.items():
            if key == format_key:
                btn.configure(bg=ACCENT_COLOR, fg="#ffffff")
            else:
                btn.configure(bg=BG_TAB, fg=TEXT_SECONDARY)

    def _update_char_count(self, text_widget, count_var, format_key):
        content = text_widget.get("1.0", tk.END).strip()
        count = len(content)
        limit = 280 if format_key != "pr_generator" else 4000
        color = SUCCESS_COLOR if count <= limit else ERROR_COLOR
        count_var.set(f"{count} / {limit} chars")
        # update label color
        for widget in text_widget.master.winfo_children():
            if isinstance(widget, tk.Label):
                widget.configure(fg=color)

    def _build_preview(self, parent):
        preview_label_font = tkfont.Font(family=FONT_FAMILY, size=9)
        tk.Label(
            parent,
            text="SCREENSHOT PREVIEW",
            bg=BG_PRIMARY,
            fg=TEXT_SECONDARY,
            font=preview_label_font,
        ).pack(anchor="w", pady=(0, 8))

        screenshot_path = self.payload.get("screenshot_path", "")

        if screenshot_path and Path(screenshot_path).exists():
            try:
                img = Image.open(screenshot_path)
                # resize to fit preview panel
                img.thumbnail((200, 300), Image.LANCZOS)
                self.screenshot_image = ImageTk.PhotoImage(img)

                img_label = tk.Label(
                    parent,
                    image=self.screenshot_image,
                    bg=BG_PRIMARY,
                    relief=tk.FLAT,
                    highlightthickness=1,
                    highlightbackground=BORDER_COLOR,
                )
                img_label.pack(anchor="n")

                # image dimensions
                orig = Image.open(screenshot_path)
                dim_font = tkfont.Font(family=FONT_FAMILY, size=9)
                tk.Label(
                    parent,
                    text=f"{orig.width} × {orig.height}px",
                    bg=BG_PRIMARY,
                    fg=TEXT_SECONDARY,
                    font=dim_font,
                ).pack(pady=(6, 0))

            except Exception as e:
                self._preview_placeholder(parent, f"Preview error:\n{str(e)[:40]}")
        else:
            self._preview_placeholder(parent, "No screenshot\navailable")

        # raw thought display
        thought = self.payload.get("raw_thought", "")
        if thought:
            tk.Frame(parent, bg=BORDER_COLOR, height=1).pack(fill=tk.X, pady=12)
            tk.Label(
                parent,
                text="RAW THOUGHT",
                bg=BG_PRIMARY,
                fg=TEXT_SECONDARY,
                font=tkfont.Font(family=FONT_FAMILY, size=9),
            ).pack(anchor="w")
            tk.Label(
                parent,
                text=thought,
                bg=BG_PRIMARY,
                fg=TEXT_PRIMARY,
                font=tkfont.Font(family=FONT_FAMILY, size=10),
                wraplength=200,
                justify=tk.LEFT,
            ).pack(anchor="w", pady=(4, 0))

    def _preview_placeholder(self, parent, message):
        tk.Label(
            parent,
            text=message,
            bg=BG_SECONDARY,
            fg=TEXT_SECONDARY,
            font=tkfont.Font(family=FONT_FAMILY, size=10),
            width=22,
            height=8,
            justify=tk.CENTER,
        ).pack()

    def _build_footer(self):
        footer = tk.Frame(self.root, bg=BG_PRIMARY, pady=12, padx=20)
        footer.pack(fill=tk.X)

        # status message
        self.status_var = tk.StringVar(value="")
        tk.Label(
            footer,
            textvariable=self.status_var,
            bg=BG_PRIMARY,
            fg=TEXT_SECONDARY,
            font=tkfont.Font(family=FONT_FAMILY, size=10),
        ).pack(side=tk.LEFT)

        # publish button
        publish_font = tkfont.Font(family=FONT_FAMILY, size=11, weight="bold")
        self.publish_btn = tk.Button(
            footer,
            text="Publish to X  →",
            bg=ACCENT_COLOR,
            fg="#ffffff",
            font=publish_font,
            relief=tk.FLAT,
            bd=0,
            padx=20,
            pady=8,
            cursor="hand2",
            command=self._handle_publish,
        )
        self.publish_btn.pack(side=tk.RIGHT)

        # copy to clipboard button
        copy_font = tkfont.Font(family=FONT_FAMILY, size=11)
        tk.Button(
            footer,
            text="Copy to clipboard",
            bg=BG_SECONDARY,
            fg=TEXT_PRIMARY,
            font=copy_font,
            relief=tk.FLAT,
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
            command=self._handle_copy,
        ).pack(side=tk.RIGHT, padx=(0, 8))

    def _handle_publish(self):
        if not self.selected_tab:
            self.status_var.set("Select a tab first.")
            return

        post_text = self.text_widgets[self.selected_tab].get("1.0", tk.END).strip()
        if not post_text:
            self.status_var.set("Post is empty — edit it first.")
            return

        self.publish_btn.configure(text="Publishing...", state=tk.DISABLED)
        self.status_var.set("")

        def publish():
            try:
                self.on_publish(
                    post_text=post_text,
                    format_key=self.selected_tab,
                    screenshot_path=self.payload.get("screenshot_path", ""),
                )
                self.root.after(0, self._on_publish_success)
            except Exception as e:
                self.root.after(0, lambda: self._on_publish_error(str(e)))

        threading.Thread(target=publish, daemon=True).start()

    def _on_publish_success(self):
        self.status_var.set("Published successfully.")
        self.publish_btn.configure(text="Published ✓", bg=SUCCESS_COLOR)
        self.root.after(2000, self.root.destroy)

    def _on_publish_error(self, error: str):
        self.status_var.set(f"Error: {error[:60]}")
        self.publish_btn.configure(
            text="Publish to X  →",
            bg=ACCENT_COLOR,
            state=tk.NORMAL,
        )

    def _handle_copy(self):
        if not self.selected_tab:
            self.status_var.set("Select a tab first.")
            return
        post_text = self.text_widgets[self.selected_tab].get("1.0", tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(post_text)
        self.status_var.set("Copied to clipboard.")

    def _center_on_screen(self):
        self.root.update_idletasks()
        w, h = 820, 580
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _bind_keys(self):
        self.root.bind("<Escape>", lambda e: self._handle_close())
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)

    def _handle_close(self):
        self.root.destroy()
        self.on_close()


# ── Public interface ──────────────────────────────────────────────────────────

def show_review(payload: dict, variations: dict, on_publish, on_close):
    """Shows the review window in a new thread."""
    def run():
        window = ReviewWindow(
            payload=payload,
            on_publish=on_publish,
            on_close=on_close,
        )
        window.show(variations)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


# ── Test ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from core.capture import run_capture
    from core.ocr import run_ocr
    from api.payload import build_payload
    from config.settings import set_project_narrative

    set_project_narrative("an AI-powered build-in-public automation tool for developers")

    print("[Review] Running full pipeline to get real generated posts...")
    capture = run_capture()
    ocr = run_ocr(capture["screenshot"]["path"])
    payload = build_payload(
        raw_thought="just built the review UI — the app is nearly complete",
        ocr_result=ocr,
        capture_result=capture,
    )

    # force Groq — bypass vision fallback for test
    payload["use_vision_fallback"] = False
    payload["screenshot_b64"] = None

    import asyncio
    from ai.generator import generate_posts
    print("[Review] Generating posts...")
    variations = asyncio.run(generate_posts(payload))

    def on_publish(post_text, format_key, screenshot_path):
        print(f"\n[Review] Publishing '{format_key}':")
        print(post_text)
        print(f"Screenshot: {screenshot_path}")

    def on_close():
        print("\n[Review] Window closed.")

    print("[Review] Opening review window...")
    window = ReviewWindow(payload=payload, on_publish=on_publish, on_close=on_close)
    window.show(variations)