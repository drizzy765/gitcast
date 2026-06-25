import sys
import os
import shutil
import subprocess
import httpx
import webbrowser

def main():
    if "--setup" in sys.argv:
        env_path = os.path.join(
            os.path.dirname(__file__), '..', '.env')
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
        print("Usage:")
        print("  gitcast \"your thought here\"  -> Quick single capture")
        print("  gitcast capture            -> Start interactive multi-shot session")
        print("  gitcast --setup            -> Setup environment variables")
        sys.exit(1)

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
            "http://127.0.0.1:8000/api/cli/trigger",
            json={"thought": thought},
            timeout=30
        )
        
        if response.status_code == 200:
            print("[Gitcast] Context captured. Opening Draft Room...")
            webbrowser.open("http://127.0.0.1:8000")
        else:
            print(f"[Gitcast Error] Failed to trigger: {response.text}")
            
    except Exception as e:
        print(f"[Gitcast Error] Connection failed: {e}")
        print("Is Gitcast running? (python -m gitcast or python main.py)")

if __name__ == "__main__":
    main()
