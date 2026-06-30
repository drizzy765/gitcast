import sys
import os
import shutil
import subprocess
import httpx
import webbrowser

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
        webbrowser.open("http://localhost:8000")

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
            webbrowser.open("http://localhost:8000")
        else:
            print(f"[Gitcast Error] Failed to trigger: {response.text}")
            
    except Exception as e:
        print(f"[Gitcast Error] Connection failed: {e}")
        print("Is Gitcast running? (python -m gitcast or python main.py)")

if __name__ == "__main__":
    main()
