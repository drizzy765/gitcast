import sys
import httpx
import webbrowser

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  sl \"your thought here\"  -> Quick single capture")
        print("  sl capture            -> Start interactive multi-shot session")
        sys.exit(1)

    command = sys.argv[1]

    if command == "capture":
        from core.screenshot_session import ScreenshotSession
        session = ScreenshotSession()
        session.run()
        return

    thought = " ".join(sys.argv[1:])
    print(f"[SL] Initializing capture with thought: '{thought}'")

    try:
        # We'll call an internal trigger endpoint or just fire the main logic
        # For v1 of the CLI, we'll keep it simple and just ping the local server
        # to trigger a capture with a forced thought.
        
        response = httpx.post(
            "http://127.0.0.1:8000/api/cli/trigger",
            json={"thought": thought},
            timeout=30
        )
        
        if response.status_code == 200:
            print("[SL] Context captured. Opening Draft Room...")
            webbrowser.open("http://127.0.0.1:8000")
        else:
            print(f"[SL Error] Failed to trigger: {response.text}")
            
    except Exception as e:
        print(f"[SL Error] Connection failed: {e}")
        print("Is Gitcast running? (python main.py)")

if __name__ == "__main__":
    main()
