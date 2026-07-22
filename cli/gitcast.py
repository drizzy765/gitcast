<<<<<<< HEAD
import sys
import os
import shutil
import subprocess
import httpx
import webbrowser

_browser_opened = False

def main():
    if "--setup" in sys.argv:
        from config.settings import get_active_env_path
        env_path = str(get_active_env_path(for_write=True))
        example_path = os.path.join(
            os.path.dirname(__file__), '..', '.env.example')
        if not os.path.exists(example_path):
            example_path = os.path.join(
                os.path.dirname(__file__), '.env.example')
        
        if not os.path.exists(env_path):
            if os.path.exists(example_path):
                shutil.copy(example_path, env_path)
            else:
                # If neither is found, create an empty or minimal env file
                with open(env_path, 'w') as f:
                    f.write("# Gitcast Environment Variables\nGROQ_API_KEY=\nGEMINI_API_KEY=\n")
        
        try:
            if sys.platform == "win32":
                subprocess.run(["notepad", env_path])
            elif sys.platform == "darwin":
                subprocess.run(["open", "-t", env_path])
            else:
                try:
                    subprocess.run(["xdg-open", env_path])
                except Exception:
                    print(f"[Gitcast] Created/configured .env at: {env_path}")
                    print("Please open it in an editor to add your API keys.")
        except Exception as e:
            print(f"[Gitcast] Created/configured .env at: {env_path}")
            print(f"Could not automatically open editor: {e}")
        sys.exit(0)

    if len(sys.argv) < 2:
        # start FastAPI server in background thread
        import threading
        import webbrowser
        import time
        import urllib.request

        def start_server():
            from api.server import start_server as run
            run()

        server_thread = threading.Thread(
            target=start_server, daemon=True)
        server_thread.start()

        # wait for server to be ready (max 5 seconds)
        for _ in range(10):
            try:
                urllib.request.urlopen(
                    "http://localhost:8000/health",
                    timeout=1)
                break
            except Exception:
                time.sleep(0.5)

        # open browser
        global _browser_opened
        if not _browser_opened:
            webbrowser.open("http://localhost:8000")
            _browser_opened = True

        # ASCII Logo
        print(" ██████╗ ██╗████████╗ ██████╗  █████╗  ███████╗████████╗")
        print("██╔════╝ ██║╚══██╔══╝██╔════╝ ██╔══██╗ ██╔════╝╚══██╔══╝")
        print("██║  ███╗██║   ██║   ██║      ███████║ ███████╗   ██║   ")
        print("██║   ██║██║   ██║   ██║      ██╔══██║ ╚════██║   ██║   ")
        print("╚██████╔╝██║   ██║   ╚██████╗ ██║  ██║ ███████║   ██║   ")
        print(" ╚═════╝ ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝ ╚══════╝   ╚═╝   ")

        from config.settings import USING_BASE_KEYS

        if USING_BASE_KEYS:
            print("> [OK] using Gitcast shared API key")
            print("> // want your own key? run: "
                  "gitcast --setup")
            print("> // get free key: console.groq.com")
        else:
            print("> [OK] using your configured API keys")

        print("[OK] server running at http://localhost:8000")
        print("[OK] browser opened")
        print("\n> [OK] Gitcast daemon is listening globally.")
        print("> Press Ctrl+Alt+S (or Ctrl+Shift+P) while coding to capture a screenshot + git diff and generate posts.\n")

        from core.tray import run_tray
        from core.trigger import on_trigger
        run_tray(trigger_callback=on_trigger)
        return

    command = sys.argv[1]

    if command == "capture":
        from core.screenshot_session import ScreenshotSession
        session = ScreenshotSession()
        session.run()
        return

    thought = " ".join(sys.argv[1:])
    print(f"[Gitcast] Initializing capture with thought: '{thought}'")

    try:
        # Call the internal trigger endpoint
        response = httpx.post(
            "http://localhost:8000/api/cli/trigger",
            json={"thought": thought},
            timeout=30
        )
        
        if response.status_code == 200:
            print("[Gitcast] Context captured. Opening Draft Room...")
        else:
            print(f"[Gitcast Error] Failed to trigger: {response.text}")
            
    except Exception as e:
        print(f"[Gitcast Error] Connection failed: {e}")
        print("Is Gitcast running? (python -m gitcast or python main.py)")

if __name__ == "__main__":
    main()
=======
import sys
import subprocess
import httpx
import webbrowser
import os
import signal

_browser_opened = False
VERSION = "1.0.27"


def handle_exit(sig=None, frame=None):
    print("\n> [Gitcast] shutting down... bye.")
    os._exit(0)


def setup():
    print("""
┌──────────────────────────────────────────────┐
│  GITCAST SETUP                               │
│  Add your own API key for unlimited usage    │
└──────────────────────────────────────────────┘

> Gitcast works out of the box with a shared key.
Add your own free key to remove rate limits.

Get a free Groq key in 2 minutes:

1. Go to console.groq.com
2. Sign up free
3. API Keys -> Create API Key
4. Copy the key starting with gsk_
""")

    try:
        key = input("> Paste your Groq key (or press Enter to skip): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n> Setup cancelled.")
        return

    if not key:
        print("> Skipped - using shared key.")
        return

    if not key.startswith("gsk_"):
        print("> [!!] That doesn't look like a Groq key (should start with gsk_)")
        print("> Setup cancelled - try again.")
        return

    from pathlib import Path

    config_dir = Path.home() / ".gitcast"
    config_dir.mkdir(exist_ok=True)
    env_file = config_dir / ".env"

    lines = []
    if env_file.exists():
        lines = env_file.read_text().splitlines()
        lines = [
            line for line in lines
            if not line.startswith("BYOK_KEY")
            and not line.startswith("BYOK_PROVIDER")
        ]

    lines.append(f"BYOK_KEY={key}")
    lines.append("BYOK_PROVIDER=groq")
    env_file.write_text("\n".join(lines))

    print("> [OK] Key saved to ~/.gitcast/.env")
    print("> [OK] Your key will be used from now on")
    print("> // restart gitcast to apply")


def check_tesseract() -> bool:
    import subprocess
    import shutil
    import os

    # Method 1: check system PATH
    tesseract_path = shutil.which("tesseract")
    if tesseract_path:
        print(f"> [OK] Tesseract OCR found")
        return True

    # Method 2: check common Windows install paths
    windows_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\{}\AppData\Local\Tesseract-OCR\tesseract.exe".format(
            os.environ.get("USERNAME", "")),
    ]
    for path in windows_paths:
        if os.path.exists(path):
            # found it — add to PATH so pytesseract
            # can use it
            tesseract_dir = os.path.dirname(path)
            os.environ["PATH"] = (
                tesseract_dir + os.pathsep +
                os.environ.get("PATH", ""))
            # also tell pytesseract directly
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = path
            except ImportError:
                pass
            print(f"> [OK] Tesseract OCR found")
            return True

    # Method 3: try running it directly
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            print("> [OK] Tesseract OCR found")
            return True
    except Exception:
        pass

    # genuinely not found — show install instructions
    print("""
> [!!] TESSERACT OCR NOT INSTALLED
>
> Required for reading your screen locally.
> Your code never leaves your machine without
> your permission - OCR runs on-device.
>
> WINDOWS:
>   Download: github.com/UB-Mannheim/tesseract/wiki
>   Run installer
>   Check "Add to PATH" during install
>   Restart terminal then run gitcast again
>
> MAC:
>   brew install tesseract
>
> LINUX:
>   sudo apt install tesseract-ocr
>
> Gitcast will still run. Posts will generate
> but screenshot text extraction is limited.
    """)
    return False


def check_server():
    from core.cloud_client import check_server_health
    import time

    print("> [Cloud] Connecting to Gitcast server...")

    # Render free tier sleeps after inactivity
    # retry up to 3 times with increasing delays
    for attempt in range(3):
        health = check_server_health()

        if health.get("status") == "ok":
            providers = health.get("providers", {})
            active = [k for k, v in providers.items()
                      if v]
            print(f"> [OK] Connected to Gitcast server")
            print(f"> [OK] Providers: "
                  f"{', '.join(active)}")
            from config.settings import BYOK_KEY
            if BYOK_KEY:
                print("> [OK] Using your own API key")
            else:
                print("> [OK] Using Gitcast shared key")
                print(">      Add your own for unlimited:")
                print(">      gitcast --setup")
            return True

        if attempt == 0:
            print("> [Cloud] Server waking up, "
                  "please wait...")
        time.sleep(8)

    # after retries still failed
    print("> [!!] Cannot reach Gitcast server")
    print(">      Posts may not generate")
    print(">      Check: "
          "https://gitcast-api.onrender.com/health")
    return False

def main():
    if "--setup" in sys.argv:
        setup()
        sys.exit(0)

    if "--version" in sys.argv:
        print(f"gitcast {VERSION}")
        return

    if len(sys.argv) < 2:
        print(f"> GITCAST v{VERSION}")
        print("> git diff -> published post.")
        print(">")
        print("> // Press Ctrl+C to quit\n")

        check_tesseract()

        # start FastAPI server in background thread
        import threading
        import time
        import urllib.request

        def start_server():
            from api.server import start_server as run
            run()

        server_thread = threading.Thread(
            target=start_server, daemon=True)
        server_thread.start()

        # wait for server to be ready (max 5 seconds)
        for _ in range(10):
            try:
                urllib.request.urlopen(
                    "http://localhost:8000/health",
                    timeout=1)
                break
            except Exception:
                time.sleep(0.5)

        # open browser
        global _browser_opened
        if not _browser_opened:
            webbrowser.open("http://localhost:8000")
            _browser_opened = True

        print("> [OK] server running at http://localhost:8000")
        print("> [OK] browser opened")
        print("> Press Ctrl+Shift+P to capture")

        check_server()

        from core.tray import run_tray
        from core.trigger import on_trigger

        # register BEFORE starting tray:
        signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)

        # wrap run_tray in try/except:
        try:
            run_tray(trigger_callback=on_trigger)
        except KeyboardInterrupt:
            handle_exit()
        return

    command = sys.argv[1]

    if command == "capture":
        from core.screenshot_session import ScreenshotSession
        session = ScreenshotSession()
        session.run()
        return

    thought = " ".join(sys.argv[1:])
    print(f"[Gitcast] Initializing capture with thought: '{thought}'")

    try:
        # Call the internal trigger endpoint
        response = httpx.post(
            "http://localhost:8000/api/cli/trigger",
            json={"thought": thought},
            timeout=30
        )
        
        if response.status_code == 200:
            print("[Gitcast] Context captured. Opening Draft Room...")
        else:
            print(f"[Gitcast Error] Failed to trigger: {response.text}")
            
    except Exception as e:
        print(f"[Gitcast Error] Connection failed: {e}")
        print("Is Gitcast running? (python -m gitcast or python main.py)")

if __name__ == "__main__":
    main()
>>>>>>> 1305f09 ( docs: update README with detailed features, CLI reference, and architecture flow)
