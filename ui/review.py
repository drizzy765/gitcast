import json
import webbrowser
from config.settings import CURRENT_DRAFT

def show_review(payload, variations, on_publish, on_close):
    """
    Tkinter review window fallback/mock.
    Saves the generated variations to current draft and opens the web dashboard.
    """
    print("[Gitcast] Mock review window triggered - saving draft and opening browser.")
    draft_data = {
        "payload": payload,
        "variations": variations,
        "timestamp": payload.get("timestamp", ""),
        "status": "ready"
    }
    try:
        with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
            json.dump(draft_data, f, indent=4)
        print("[Gitcast] Draft saved successfully.")
    except Exception as e:
        print(f"[Gitcast] Failed to save draft: {e}")
        
    on_close()
