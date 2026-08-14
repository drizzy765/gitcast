import os
import subprocess
import time
from pathlib import Path
from datetime import datetime
from config.settings import STORAGE_DIR
from core.log_stream import stream_log
from api.analytics import track
BASE_DIR = STORAGE_DIR.parent.parent
screenshot_dir = STORAGE_DIR / "screenshots"
screenshot_dir.mkdir(parents=True, exist_ok=True)
from .framing import add_programming_frame


GIT_DIFF_EXCLUDES = [
    ":(exclude)config/session_token.txt",
    ":(exclude)storage/data/**",
    ":(exclude).playwright-mcp/**",
    ":(exclude)memory.md",
    ":(exclude)*gitcast-app*.png",
]


# ── Screenshot capture ────────────────────────────────────────────────────────

def capture_active_window(delay: float = 5.0) -> dict:
    """
    Takes a screenshot of the entire screen and saves it to storage/data/screenshots.
    Returns a dict with the image path and dimensions.
    """
    if delay > 0:
        if delay < 1.0:
            # Short buffer delay
            time.sleep(delay)
        else:
            # Full countdown delay
            stream_log("Capture", "INFO", f"starting in {int(delay)}s; switch to target window")
            for i in range(int(delay), 0, -1):
                print(f"  {i}...")
                # Terminal bell (ASCII 7)
                import sys
                sys.stdout.write('\a')
                sys.stdout.flush()
                time.sleep(1)

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

    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # primary monitor
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.save(str(filepath))
            width = screenshot.width
            height = screenshot.height
    except Exception as exc:
        try:
            img = Image.new("RGB", (1920, 1080), color=(30, 30, 30))
            img.save(str(filepath))
            stream_log("Capture", "WARN", f"MSS capture failed ({exc}). Created blank fallback screenshot.")
            width = 1920
            height = 1080
        except Exception as fallback_exc:
            return {
                "success": False,
                "path": "",
                "width": 0,
                "height": 0,
                "timestamp": timestamp,
                "error": f"MSS failed: {exc}, Fallback failed: {fallback_exc}",
                "reason": "capture_failed",
            }

    # Return relative path for web/API consistency
    relative_path = str(filepath.relative_to(BASE_DIR)).replace("\\", "/")
    stream_log("Capture", "OK", f"screenshot saved: {relative_path}")

    return {
        "success": True,
        "path": relative_path,
        "width": width,
        "height": height,
        "timestamp": timestamp,
        "error": "",
        "reason": "ok",
    }


# ── Git diff extraction ───────────────────────────────────────────────────────

def get_git_diff(cwd: str = None) -> dict:
    """
    Runs git diff in the given directory.
    Falls back to staged changes, recent commits (HEAD~1 HEAD), or untracked files
    so that already-committed changes are still detected cleanly.
    """
    target_dir = cwd or str(Path.home())

    try:
        # 1. Uncommitted working tree diff vs HEAD
        diff_cmd = ["git", "diff", "HEAD", "--", ".", *GIT_DIFF_EXCLUDES]
        result = subprocess.run(
            diff_cmd,
            cwd=target_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )

        diff_text = result.stdout.strip()

        if result.returncode != 0:
            return {
                "success": False,
                "diff": "",
                "error": "not a git repository",
                "reason": "no_git",
            }

        # 2. Try staged changes
        if not diff_text:
            staged = subprocess.run(
                ["git", "diff", "--cached", "--", ".", *GIT_DIFF_EXCLUDES],
                cwd=target_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            diff_text = staged.stdout.strip()

        # 3. Fallback: If working tree is clean, check recent commit diff (HEAD~1 HEAD or HEAD show)
        is_recent_commit = False
        if not diff_text:
            recent = subprocess.run(
                ["git", "diff", "HEAD~1", "HEAD", "--", ".", *GIT_DIFF_EXCLUDES],
                cwd=target_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            diff_text = recent.stdout.strip()
            if not diff_text:
                show_cmd = subprocess.run(
                    ["git", "show", "--stat", "-p", "HEAD", "--", ".", *GIT_DIFF_EXCLUDES],
                    cwd=target_dir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5,
                )
                diff_text = show_cmd.stdout.strip()
            if diff_text:
                is_recent_commit = True

        # 4. Check for untracked files if diff is still empty
        if not diff_text:
            status_cmd = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=target_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            untracked = [line for line in status_cmd.stdout.splitlines() if line.startswith("??")]
            if untracked:
                diff_text = "New untracked files:\n" + "\n".join(untracked[:15])

        prefix = "[Recent Commit Diff]\n" if is_recent_commit else ""
        full_diff = (prefix + diff_text)[:3500]

        return {
            "success": True,
            "diff": full_diff,
            "is_recent_commit": is_recent_commit,
            "error": "",
            "reason": "recent_commit" if is_recent_commit else ("ok" if full_diff else "no_changes"),
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
    Returns the actual cwd gitcast was launched from.
    Does NOT fall back to unrelated directories like
    context-engine's own install path or Path.home().
    """
    import sys
    cwd = os.getcwd()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32" else 0,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return cwd  # not a git repo — return cwd as-is


def run_capture(delay: float = 5.0) -> dict:
    working_dir = detect_working_directory()
    screenshot = capture_active_window(delay=delay)
    
    # Apply programming frame if capture succeeded
    if screenshot.get("success") and screenshot.get("path"):
        try:
            abs_path = str(screenshot_dir / Path(screenshot["path"]).name)
            framed_path = add_programming_frame(abs_path)
            rel_framed_path = str(Path(framed_path).relative_to(BASE_DIR)).replace("\\", "/")
            screenshot["framed_path"] = rel_framed_path
            # By default, use the framed path for downstream preview/publishing
            screenshot["raw_path"] = screenshot["path"]
            screenshot["path"] = rel_framed_path
        except Exception as e:
            stream_log("Capture", "WARN", f"framing failed: {e}")
            screenshot["framed_path"] = ""

    git_diff = get_git_diff(working_dir)
    if screenshot.get("success"):
        track("capture_completed", {
            "has_git_diff": bool(git_diff.get("diff")),
            "ocr_confidence": 0,
            "ocr_reliable": False,
        })
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
