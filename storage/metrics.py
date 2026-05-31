import json
from datetime import datetime

from config.settings import METRICS_LOG, POST_LOG
from storage.logger import load_posts, save_posts


def _normalise_metrics(post_id: str, metrics: dict) -> dict:
    return {
        "post_id": post_id,
        "impressions": int(metrics.get("impressions", 0)),
        "likes": int(metrics.get("likes", 0)),
        "comments": int(metrics.get("comments", 0)),
        "reposts": int(metrics.get("reposts", 0)),
        "hashtags": [str(tag).strip()[:40] for tag in metrics.get("hashtags", []) if str(tag).strip()][:10],
        "measured_at": metrics.get("measured_at") or datetime.now().isoformat(),
        "days_after_post": int(metrics.get("days_after_post", 1)),
    }


def save_metrics(post_id: str, metrics: dict) -> dict:
    entry = _normalise_metrics(post_id, metrics)
    METRICS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(METRICS_LOG, "a", encoding="utf-8") as file:
        file.write(json.dumps(entry) + "\n")

    posts = load_posts()
    for post in posts:
        if post.get("id") == post_id or post.get("timestamp") == post_id:
            post["metrics"] = entry
            break
    save_posts(posts)
    return {"success": True}


def get_all_metrics() -> list:
    if not METRICS_LOG.exists():
        return []
    entries = []
    with open(METRICS_LOG, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def get_metrics(post_id: str) -> dict:
    latest = {}
    for entry in get_all_metrics():
        if entry.get("post_id") == post_id:
            latest = entry
    return latest


if __name__ == "__main__":
    print(f"[Metrics] Loaded {len(get_all_metrics())} metrics entries from {METRICS_LOG}")
