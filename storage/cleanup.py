import os
import time
from pathlib import Path
from config.settings import STORAGE_DIR, screenshot_retention_hours

# [Cleanup] module for managing screenshot retention policy

def run_cleanup():
    """Deletes screenshots older than screenshot_retention_hours."""
    screenshots_dir = STORAGE_DIR / "screenshots"
    if not screenshots_dir.exists():
        print("[Cleanup] No screenshots directory found.")
        return

    now = time.time()
    retention_sec = screenshot_retention_hours * 3600
    deleted_count = 0
    
    for file_path in screenshots_dir.glob("*.png"):
        file_age = now - file_path.stat().st_mtime
        if file_age > retention_sec:
            try:
                # Use secure delete if possible, but for cleanup standard unlink is usually fine
                # unless the user specifically wants secure delete for all old files.
                # Given core/security.py exists, we could use it, but it might be overkill for bulk cleanup.
                file_path.unlink()
                deleted_count += 1
            except Exception as e:
                print(f"[Cleanup] Error deleting {file_path.name}: {e}")

    if deleted_count > 0:
        print(f"[Cleanup] Deleted {deleted_count} old screenshots.")
    else:
        print("[Cleanup] No old screenshots to delete.")

def get_storage_stats():
    """Returns count of screenshots, total size in MB, and oldest file date."""
    screenshots_dir = STORAGE_DIR / "screenshots"
    if not screenshots_dir.exists():
        return {"count": 0, "total_size_mb": 0.0, "oldest_file": "N/A"}

    files = list(screenshots_dir.glob("*.png"))
    if not files:
        return {"count": 0, "total_size_mb": 0.0, "oldest_file": "N/A"}

    total_size = sum(f.stat().st_size for f in files)
    oldest_time = min(f.stat().st_mtime for f in files)
    oldest_date = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(oldest_time))

    return {
        "count": len(files),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "oldest_file": oldest_date
    }

if __name__ == "__main__":
    print("=== STORAGE CLEANUP TEST ===")
    stats = get_storage_stats()
    print(f"Current stats: {stats}")
    run_cleanup()
