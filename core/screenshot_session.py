import time
import sys
import webbrowser
import json
import threading
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Prompt
from rich import box
from pynput import keyboard
from core.capture import capture_active_window, detect_working_directory, get_git_diff
from core.ocr import run_ocr
from core.security import scan_for_secrets, delete_capture
from config.settings import STORAGE_DIR, CURRENT_DRAFT, get_project_narrative

console = Console()

class ScreenshotSession:
    def __init__(self):
        self.screenshots = []
        self.max_shots = 6
        self.done = False
        self.cancelled = False
        self.working_dir = detect_working_directory()
        self.git_diff = get_git_diff(self.working_dir)
        self.accent_color = "#6366f1"
        self._lock = threading.Lock()
        self._processing = False

    def run(self):
        """Starts the interactive terminal session."""
        self.show_header()
        
        # Start hotkey listener
        with keyboard.Listener(on_press=self.on_press) as listener:
            try:
                while not self.done and not self.cancelled:
                    if len(self.screenshots) >= self.max_shots:
                        if not self._processing:
                            console.print(f"\n[bold {self.accent_color}]Limit of {self.max_shots} reached. Moving to final review...[/bold {self.accent_color}]")
                            time.sleep(1.5)
                            self.done = True
                            break
                    time.sleep(0.1)
            except KeyboardInterrupt:
                self.cancelled = True
            
            # Stop listener to free up stdin for Prompts
            listener.stop()

        if self.cancelled:
            console.print("\n[red]Session cancelled. No screenshots saved.[/red]")
            return []

        # Remove any screenshots that might have failed
        self.screenshots = [s for s in self.screenshots if s.get("path")]

        if not self.screenshots:
            console.print("[yellow]No screenshots captured.[/yellow]")
            return []

        # BATCH REVIEW & TAGGING
        # Now we ask for purposes and keep/discard all at once
        self.review_and_tag_shots()
        
        if self.screenshots:
            self.finish_session()
            return self.screenshots
        else:
            console.print("[yellow]All shots discarded. Nothing to post.[/yellow]")
            return []

    def show_header(self):
        header = Panel(
            f"Capture up to [bold]{self.max_shots}[/bold] screenshots. Tag them all at the end.\n\n"
            f"[bold {self.accent_color}]Ctrl+S[/bold {self.accent_color}]  →  [white]Capture Now (Instant)[/white]\n"
            f"[bold {self.accent_color}]Ctrl+D[/bold {self.accent_color}]  →  [white]Done & Review[/white]\n"
            f"[bold {self.accent_color}]Ctrl+C[/bold {self.accent_color}]  →  [white]Cancel[/white]",
            title=f"[bold {self.accent_color}]CONTEXT ENGINE[/bold {self.accent_color}]  ·  Rapid Capture Mode",
            expand=False,
            border_style=self.accent_color,
            box=box.ROUNDED,
            padding=(1, 2)
        )
        console.print(header)

    def on_press(self, key):
        """Handles session hotkeys."""
        try:
            # Ctrl+S (\x13)
            if hasattr(key, 'char') and key.char == '\x13':
                if self._processing:
                    # Very brief message so it doesn't clutter
                    console.print("[dim]...waiting for current capture...[/dim]", end="\r")
                else:
                    threading.Thread(target=self.take_screenshot, daemon=True).start()
            
            # Ctrl+D (\x04)
            elif hasattr(key, 'char') and key.char == '\x04':
                if not self._processing:
                    self.done = True
                    return False
                
            # Ctrl+C (\x03)
            elif hasattr(key, 'char') and key.char == '\x03':
                self.cancelled = True
                return False
        except Exception:
            pass

    def take_screenshot(self):
        """Captures window silently and adds to queue."""
        with self._lock:
            self._processing = True
            try:
                # Minimal 1s countdown for focus shift
                for i in range(1, 0, -1):
                    time.sleep(0.5)
                
                shot = capture_active_window(delay=0.1)
                if not shot["success"]:
                    console.print(f"[red]Capture failed: {shot['error']}[/red]")
                    return

                # OCR and Security (Silent progress)
                ocr = run_ocr(shot["path"])
                security = scan_for_secrets(ocr["text"] or ocr["raw_text"])

                if not security["clean"]:
                    console.print(f"\n[red]⚠️  Shot {len(self.screenshots)+1} blocked (sensitive content).[/red]")
                    delete_capture(shot["path"])
                    return

                # Add to list with default purpose
                screenshot_data = {
                    "path": shot["path"],
                    "purpose": "code", 
                    "ocr_text": ocr["text"] or ocr["raw_text"],
                    "confidence": ocr["confidence"],
                    "timestamp": shot["timestamp"],
                    "index": len(self.screenshots) + 1
                }
                self.screenshots.append(screenshot_data)
                
                # Non-blocking success message
                console.print(f"[bold green]✓[/bold green] Captured Shot {len(self.screenshots)}  ·  [dim]Press Ctrl+S for more or Ctrl+D to finish[/dim]")
                
            finally:
                self._processing = False

    def review_and_tag_shots(self):
        """Final phase where user tags and picks shots."""
        console.print(Panel(
            "REVIEW & TAG YOUR SESSION\n[dim]Assign purposes and decide what to keep[/dim]", 
            style=f"bold {self.accent_color}", 
            border_style=self.accent_color,
            box=box.DOUBLE
        ))
        
        keeps = [True] * len(self.screenshots)
        
        while True:
            table = Table(show_header=True, border_style=self.accent_color, box=box.ROUNDED)
            table.add_column("ID", justify="center")
            table.add_column("Preview", width=40)
            table.add_column("Purpose")
            table.add_column("Status")
            
            for i, (s, keep) in enumerate(zip(self.screenshots, keeps), 1):
                status = "[green]Keep[/green]" if keep else "[red]Discard[/red]"
                check = "[bold green]✓[/bold green]" if keep else "[ ]"
                preview = (s["ocr_text"][:37].replace("\n", " ") + "...") if s["ocr_text"] else "No text"
                table.add_row(f"{check} {i}", preview, f"[bold]{s['purpose']}[/bold]", status)
            
            console.print(table)
            console.print("[dim]Commands: [ID] to toggle status | [pID] to set purpose (e.g. p1) | [d] done[/dim]")
            action = Prompt.ask("Action", default="d")
            
            if action.lower() == 'd':
                break
            
            # Purpose setting (e.g. p1)
            if action.lower().startswith('p') and len(action) > 1:
                try:
                    idx = int(action[1:]) - 1
                    if 0 <= idx < len(self.screenshots):
                        purpose = Prompt.ask(
                            f"Purpose for Shot {idx+1}",
                            choices=["code", "terminal", "browser", "result", "other"],
                            default=self.screenshots[idx]["purpose"]
                        )
                        self.screenshots[idx]["purpose"] = purpose
                except ValueError:
                    pass
                continue

            # Toggle keep/discard
            try:
                idx = int(action) - 1
                if 0 <= idx < len(keeps):
                    keeps[idx] = not keeps[idx]
            except ValueError:
                console.print("[red]Invalid command.[/red]")
                
        # Final cleanup
        final_shots = []
        for s, keep in zip(self.screenshots, keeps):
            if keep:
                final_shots.append(s)
            else:
                delete_capture(s["path"])
        
        self.screenshots = final_shots

    def finish_session(self):
        """Saves session and opens dashboard."""
        console.print(Panel(
            "[bold green]✓ Session Complete[/bold green]\n"
            "Opening dashboard to finish your post...",
            border_style="green",
            box=box.ROUNDED,
            padding=(1, 2)
        ))
        
        self.save_session_and_generate()
        webbrowser.open("http://localhost:8000")

    def save_session_and_generate(self):
        """Background generation of post variations."""
        from api.payload import build_payload
        from ai.generator import generate_posts
        import asyncio

        payload = build_payload(
            raw_thought="",
            ocr_result={}, 
            capture_result={"working_dir": self.working_dir, "git_diff": self.git_diff, "screenshot": self.screenshots[0]},
            multi_screenshots=self.screenshots
        )
        
        draft_data = {
            "payload": payload,
            "variations": {},
            "timestamp": payload["timestamp"],
            "status": "generating"
        }
        with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
            json.dump(draft_data, f, indent=4)

        def run_gen():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                variations = loop.run_until_complete(generate_posts(payload))
                draft_data["variations"] = variations
                draft_data["status"] = "ready"
                with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
                    json.dump(draft_data, f, indent=4)
            except Exception:
                pass

        threading.Thread(target=run_gen, daemon=True).start()

if __name__ == "__main__":
    session = ScreenshotSession()
    session.run()
