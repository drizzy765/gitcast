import os
import subprocess
import time
from pathlib import Path
from datetime import datetime
from config.settings import STORAGE_DIR
from .framing import add_programming_frame


# ── Screenshot capture ────────────────────────────────────────────────────────

def capture_active_window() -> dict:
    """
    Takes a screenshot of the entire screen and saves it to storage/data/screenshots.
    Returns a dict with the image path and dimensions.
    """
    # Small delay to allow UI to settle (e.g. hide hotkey-triggered popups)
    time.sleep(0.5)

    screenshot_dir = STORAGE_DIR / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"capture_{timestamp}.png"
    filepath = screenshot_dir / filename

    try:
        import mss
        from PIL import Image
    except ImportError as exc:
        return {
            "success": False,
            "path": "",
            "width": 0,
            "height": 0,
            "timestamp": timestamp,
            "error": str(exc),
            "reason": "missing_dependency",
        }

    with mss.mss() as sct:
        monitor = sct.monitors[1]  # primary monitor
        screenshot = sct.grab(monitor)
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        img.save(str(filepath))

    return {
        "success": True,
        "path": str(filepath),
        "width": screenshot.width,
        "height": screenshot.height,
        "timestamp": timestamp,
        "error": "",
        "reason": "ok",
    }


# ── Git diff extraction ───────────────────────────────────────────────────────

def get_git_diff(cwd: str = None) -> dict:
    """
    Runs git diff HEAD in the given directory.
    Falls back to the user's home directory if no cwd is given.
    Returns a dict with the diff text and a status flag.
    """
    target_dir = cwd or str(Path.home())

    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )

        diff_text = result.stdout.strip()

        if result.returncode != 0:
            return {
                "success": False,
                "diff": "",
                "error": result.stderr.strip(),
                "reason": "git_error",
            }

        if not diff_text:
            # try staged changes if working tree diff is empty
            staged = subprocess.run(
                ["git", "diff", "--cached"],
                cwd=target_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            diff_text = staged.stdout.strip()

        return {
            "success": True,
            "diff": diff_text[:3000],  # cap at 3000 chars to stay inside token limits
            "error": "",
            "reason": "ok" if diff_text else "no_changes",
        }

    except FileNotFoundError:
        return {
            "success": False,
            "diff": "",
            "error": "git not found",
            "reason": "no_git",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "diff": "",
            "error": "git diff timed out",
            "reason": "timeout",
        }
    except Exception as e:
        return {
            "success": False,
            "diff": "",
            "error": str(e),
            "reason": "unknown",
        }


# ── Detect working directory ──────────────────────────────────────────────────

def detect_working_directory() -> str:
    """
    Attempts to find the most likely git repo the user is working in.
    Checks the script's own directory first, then walks up from cwd.
    """
    candidates = [
        Path(__file__).resolve().parent.parent,  # project root
        Path.cwd(),
        Path(os.environ.get("USERPROFILE", "")) / "Documents" / "context-engine",
        Path.home(),
    ]

    for candidate in candidates:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(candidate),
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            continue

    return str(Path.home())


def run_capture() -> dict:
    working_dir = detect_working_directory()
    screenshot = capture_active_window()
    
    # Apply programming frame if capture succeeded
    if screenshot.get("success") and screenshot.get("path"):
        try:
            framed_path = add_programming_frame(screenshot["path"])
            screenshot["framed_path"] = framed_path
            # By default, use the framed path for downstream preview/publishing
            screenshot["raw_path"] = screenshot["path"]
            screenshot["path"] = framed_path
        except Exception as e:
            print(f"[Capture] Framing failed: {e}")
            screenshot["framed_path"] = ""

    git_diff = get_git_diff(working_dir)
    return {
        "screenshot": screenshot,
        "working_dir": working_dir,
        "git_diff": git_diff,
        "timestamp": screenshot.get("timestamp", datetime.now().strftime("%Y%m%d_%H%M%S")),
    }


# ── Test ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = run_capture()
    print("\n=== CAPTURE RESULT ===")
    print(f"Screenshot success: {result['screenshot'].get('success')}")
    print(f"Screenshot: {result['screenshot']['path']}")
    print(f"Working dir: {result['working_dir']}")
    print(f"Git diff success: {result['git_diff']['success']}")
    print(f"Git diff reason: {result['git_diff']['reason']}")
    if result["screenshot"].get("error"):
        print(f"Screenshot error: {result['screenshot']['error']}")
    if result['git_diff']['diff']:
        print(f"Diff preview:\n{result['git_diff']['diff'][:200]}...")
