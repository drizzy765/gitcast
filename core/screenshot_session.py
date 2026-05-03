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

    def run(self):
        # Display Start Header
        self.show_header()
        
        # Start listener in a non-blocking way
        # Using suppress=True to try and keep the terminal clean
        with keyboard.Listener(on_press=self.on_press) as listener:
            try:
                while not self.done and not self.cancelled:
                    if len(self.screenshots) >= self.max_shots:
                        console.print(f"\n[{self.accent_color}]Maximum screenshots (6) reached. Finalizing session...[/{self.accent_color}]")
                        time.sleep(1)
                        self.done = True
                        break
                    time.sleep(0.1)
            except KeyboardInterrupt:
                self.cancelled = True
            
            if self.cancelled:
                console.print("\n[red]Session cancelled.[/red]")
                return []

            if not self.screenshots:
                console.print("[yellow]No screenshots captured. Exiting.[/yellow]")
                return []

            # Stop listener before review to avoid conflicts with input
            listener.stop()

        # Review shots
        self.review_shots()
        
        # Session complete
        if self.screenshots:
            self.finish_session()
            return self.screenshots
        else:
            console.print("[yellow]All shots discarded. Exiting.[/yellow]")
            return []

    def show_header(self):
        header = Panel(
            "[white]Capture up to 6 screenshots for your post[/white]\n\n"
            f"[bold {self.accent_color}]Ctrl+S[/bold {self.accent_color}]  →  Take screenshot\n"
            f"[bold {self.accent_color}]Ctrl+D[/bold {self.accent_color}]  →  Done / finish session\n"
            f"[bold {self.accent_color}]Ctrl+C[/bold {self.accent_color}]  →  Cancel session",
            title=f"[bold {self.accent_color}]CONTEXT ENGINE[/bold {self.accent_color}]  ·  Screenshot Session",
            expand=False,
            border_style=self.accent_color,
            box=box.ROUNDED
        )
        console.print(header)

    def on_press(self, key):
        try:
            # Ctrl+S (\x13)
            if hasattr(key, 'char') and key.char == '\x13':
                threading.Thread(target=self.take_screenshot).start()
            
            # Ctrl+D (\x04)
            elif hasattr(key, 'char') and key.char == '\x04':
                self.done = True
                return False
                
            # Ctrl+C (\x03)
            elif hasattr(key, 'char') and key.char == '\x03':
                self.cancelled = True
                return False
        except Exception:
            pass

    def take_screenshot(self):
        # Countdown with Spinner
        with Live(console=console, transient=True) as live:
            for i in range(3, 0, -1):
                live.update(Panel(
                    f"[bold {self.accent_color}]{i}...[/bold {self.accent_color}]", 
                    title="Get Ready", 
                    border_style=self.accent_color,
                    padding=(1, 5)
                ))
                time.sleep(1)
            
            live.update(Panel(
                "CAPTURING...", 
                style=f"bold white on {self.accent_color}",
                border_style="white"
            ))
            time.sleep(0.2)
        
        shot = capture_active_window(delay=0.1)
        if not shot["success"]:
            console.print(f"[red]Capture failed: {shot['error']}[/red]")
            return

        # OCR and Security scan with progress
        with Progress(
            SpinnerColumn(spinner_name="dots", style=self.accent_color),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(complete_style=self.accent_color),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("Scanning for secrets...", total=100)
            ocr = run_ocr(shot["path"])
            progress.update(task, completed=50)
            security = scan_for_secrets(ocr["text"] or ocr["raw_text"])
            progress.update(task, completed=100)

        if not security["clean"]:
            console.print(Panel(
                "⚠️  Shot blocked — possible API key or secret detected\n"
                "Screenshot deleted. Press Ctrl+S to try again.",
                title="Security Alert",
                style="bold white on red",
                border_style="red"
            ))
            delete_capture(shot["path"])
            return

        # Success info
        console.print(f"\n[green]✓[/green] Shot {len(self.screenshots)+1} captured  ·  [dim]{Path(shot['path']).name}[/dim]")
        console.print(f"   Confidence: [bold]{ocr['confidence']}%[/bold]  ·  {len(ocr['text'] or ocr['raw_text'])} chars extracted")
        
        # Purpose tag
        purpose = Prompt.ask(
            "   Purpose? (code/terminal/browser/result/other)",
            choices=["code", "terminal", "browser", "result", "other"],
            default="code"
        )
        
        screenshot_data = {
            "path": shot["path"],
            "purpose": purpose,
            "ocr_text": ocr["text"] or ocr["raw_text"],
            "confidence": ocr["confidence"],
            "timestamp": shot["timestamp"],
            "index": len(self.screenshots) + 1
        }
        self.screenshots.append(screenshot_data)
        
        self.show_roll()

    def show_roll(self):
        table = Table(
            title=f"SESSION ROLL ({len(self.screenshots)}/6 shots taken)", 
            border_style=self.accent_color, 
            title_style=f"bold {self.accent_color}",
            box=box.SIMPLE_HEAD
        )
        table.add_column("#", justify="center", style=self.accent_color)
        table.add_column("Content Preview", style="dim", width=40)
        table.add_column("Purpose", style="bold")
        
        for i, s in enumerate(self.screenshots, 1):
            preview = (s["ocr_text"][:37].replace("\n", " ") + "...") if s["ocr_text"] else "No text extracted"
            table.add_row(f"✓ {i}", preview, s["purpose"])
            
        console.print(table)
        console.print(f"Take another? [bold {self.accent_color}]Ctrl+S[/bold {self.accent_color}] · [bold {self.accent_color}]Ctrl+D[/bold {self.accent_color}] when done ({6-len(self.screenshots)} remaining)\n")

    def review_shots(self):
        console.print(Panel(
            "REVIEW YOUR SHOTS\n[dim]Toggle keep/discard before finalizing[/dim]", 
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
                check = f"[bold {self.accent_color}]✓[/bold {self.accent_color}]" if keep else "[ ]"
                preview = (s["ocr_text"][:37].replace("\n", " ") + "...") if s["ocr_text"] else "No text"
                table.add_row(f"{check} {i}", preview, s["purpose"], status)
            
            console.print(table)
            action = Prompt.ask(
                "Select ID to toggle or '[bold green]d[/bold green]' for done",
                default="d"
            )
            
            if action.lower() == 'd':
                break
            
            try:
                idx = int(action) - 1
                if 0 <= idx < len(keeps):
                    keeps[idx] = not keeps[idx]
                else:
                    console.print("[red]Invalid ID[/red]")
            except ValueError:
                console.print("[red]Enter a number or 'd'[/red]")
                
        # Cleanup discarded
        final_shots = []
        for s, keep in zip(self.screenshots, keeps):
            if keep:
                final_shots.append(s)
            else:
                delete_capture(s["path"])
        
        self.screenshots = final_shots

    def finish_session(self):
        console.print(Panel(
            f"✓ Session complete  ·  {len(self.screenshots)} shots ready\n"
            f"[dim]Opening dashboard at localhost:8000/draft ...[/dim]",
            style="bold green",
            border_style="green",
            box=box.ROUNDED
        ))
        
        # Save to draft room and trigger generation
        self.save_session_and_generate()
        
        # Use the specific URL mentioned in requirements
        webbrowser.open("http://127.0.0.1:8000")

    def save_session_and_generate(self):
        from api.payload import build_payload
        from ai.generator import generate_posts
        import asyncio

        # Build payload with multi-screenshot support
        payload = build_payload(
            raw_thought="",
            ocr_result={}, 
            capture_result={"working_dir": self.working_dir, "git_diff": self.git_diff, "screenshot": self.screenshots[0]},
            multi_screenshots=self.screenshots
        )
        
        # Initial save (status: generating)
        draft_data = {
            "payload": payload,
            "variations": {},
            "timestamp": payload["timestamp"],
            "status": "generating"
        }
        with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
            json.dump(draft_data, f, indent=4)

        # Background generation
        def run_gen():
            try:
                # Use a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                variations = loop.run_until_complete(generate_posts(payload))
                
                draft_data["variations"] = variations
                draft_data["status"] = "ready"
                with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
                    json.dump(draft_data, f, indent=4)
            except Exception as e:
                # Silently fail in background but log if needed
                pass

        threading.Thread(target=run_gen, daemon=True).start()

if __name__ == "__main__":
    session = ScreenshotSession()
    session.run()
