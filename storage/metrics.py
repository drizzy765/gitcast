import json
from datetime import datetime
from typing import Optional


def _normalise_metrics(post_id: str, metrics: dict) -> dict:
    return {
        "post_id": post_id,
        "impressions": int(metrics.get("impressions", 0)),
        "likes": int(metrics.get("likes", 0)),
        "comments": int(metrics.get("comments", 0)),
        "reposts": int(metrics.get("reposts", 0)),
        "hashtags": [str(tag).strip()[:40] for tag in metrics.get("hashtags", []) if str(tag).strip()][:10],
        "platform": str(metrics.get("platform", "")).strip()[:40],
        "measured_at": metrics.get("measured_at") or datetime.now().isoformat(),
        "days_after_post": int(metrics.get("days_after_post", 1)),
    }


def save_metrics(post_id: str, metrics: dict, user_id: Optional[str] = None) -> dict:
    from storage.logger import load_posts, save_posts
    from config.settings import METRICS_LOG

    entry = _normalise_metrics(post_id, metrics)
    payload = {
        "impressions": entry["impressions"],
        "likes": entry["likes"],
        "comments": entry["comments"],
        "reposts": entry["reposts"],
        "hashtags": entry["hashtags"],
        "platform": entry["platform"] or "twitter",
        "days_after_post": entry["days_after_post"],
        "metrics_saved": True,
        "metrics_saved_at": entry["measured_at"],
    }

    posts = load_posts(user_id)
    found = False
    for post in posts:
        if post.get("id") == post_id:
            post.update(payload)
            found = True
            break

    if found:
        save_posts(posts)

    try:
        metrics_log = []
        if METRICS_LOG.exists() and METRICS_LOG.stat().st_size > 0:
            with open(METRICS_LOG, "r", encoding="utf-8") as f:
                metrics_log = json.load(f)
        existing = False
        for m in metrics_log:
            if m.get("post_id") == post_id:
                m.update({"post_id": post_id, **payload})
                existing = True
                break
        if not existing:
            metrics_log.append({"post_id": post_id, **payload})
        METRICS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(METRICS_LOG, "w", encoding="utf-8") as f:
            json.dump(metrics_log, f, indent=4)
    except Exception:
        pass

    return {"success": True}


def get_all_metrics(user_id: Optional[str] = None) -> list:
    from storage.logger import load_posts
    posts = load_posts(user_id)
    entries = []
    for post in posts:
        if post.get("metrics_saved"):
            entries.append({
                "post_id": post.get("id"),
                "impressions": post.get("impressions") or 0,
                "likes": post.get("likes") or 0,
                "comments": post.get("comments") or 0,
                "reposts": post.get("reposts") or 0,
                "hashtags": post.get("hashtags") or [],
                "platform": post.get("platform") or "",
                "measured_at": post.get("metrics_saved_at") or "",
                "days_after_post": post.get("days_after_post") or 0,
            })
    return entries


def get_metrics(post_id: str, user_id: Optional[str] = None) -> dict:
    from storage.logger import load_posts
    posts = load_posts(user_id)
    for post in posts:
        if post.get("id") == post_id and post.get("metrics_saved"):
            return {
                "post_id": post_id,
                "impressions": post.get("impressions") or 0,
                "likes": post.get("likes") or 0,
                "comments": post.get("comments") or 0,
                "reposts": post.get("reposts") or 0,
                "hashtags": post.get("hashtags") or [],
                "platform": post.get("platform") or "",
                "measured_at": post.get("metrics_saved_at") or "",
                "days_after_post": post.get("days_after_post") or 0,
            }
    return {}


if __name__ == "__main__":
    print("[Metrics] Local metrics module loaded")
