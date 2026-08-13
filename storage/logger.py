import json
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4


def _normalize_entry(entry: dict) -> dict:
    timestamp = entry.get("timestamp") or entry.get("created_at") or ""
    tweet_url = entry.get("tweet_url", "") or entry.get("post_url", "") or ""
    return {
        **entry,
        "id": str(entry.get("id", "")),
        "timestamp": timestamp,
        "posted_verified": bool(entry.get("posted_verified", False)),
        "posted_declined": bool(entry.get("declined", False) or entry.get("posted_declined", False)),
        "post_url": tweet_url,
        "verified_at": entry.get("verified_at", "") or "",
        "metrics": {
            "impressions": int(entry.get("impressions") or 0),
            "likes": int(entry.get("likes") or 0),
            "comments": int(entry.get("comments") or 0),
            "reposts": int(entry.get("reposts") or 0),
            "hashtags": entry.get("hashtags") or [],
            "platform": entry.get("platform") or "",
            "days_after_post": int(entry.get("days_after_post") or 0),
            "measured_at": entry.get("metrics_saved_at") or "",
        } if entry.get("metrics_saved") else {},
    }


def _load_local_posts() -> list:
    from config.settings import POST_LOG
    if not POST_LOG.exists() or POST_LOG.stat().st_size == 0:
        return []
    try:
        with open(POST_LOG, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [_normalize_entry(e) for e in data]
            return []
    except Exception:
        return []


def _save_to_local(entry: dict) -> None:
    from config.settings import POST_LOG
    posts = _load_local_posts()
    entry_id = entry.get("id")
    found = False
    if entry_id:
        for i, p in enumerate(posts):
            if p.get("id") == entry_id:
                posts[i] = {**p, **entry}
                found = True
                break
    if not found:
        posts.append(entry)
    POST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(POST_LOG, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=4)


def save_posts(posts: list, user_id: Optional[str] = None) -> None:
    from config.settings import POST_LOG
    POST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(POST_LOG, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=4)


def log_post(
    post_text: str,
    format_key: str,
    screenshot_path: str = "",
    tweet_url: str = "",
    tweet_id: str = "",
    fallback: bool = False,
    timestamp: str = "",
    user_id: Optional[str] = None,
    provider_used: str = "",
) -> Optional[str]:
    entry = {
        "id": str(uuid4()),
        "post_text": post_text,
        "format_key": format_key,
        "screenshot_path": screenshot_path,
        "tweet_url": tweet_url,
        "tweet_id": tweet_id,
        "fallback": fallback,
        "timestamp": timestamp or datetime.now().isoformat(),
        "user_id": user_id or "local",
        "provider_used": provider_used or ("fallback" if fallback else ""),
        "posted_verified": bool(tweet_url),
        "declined": False,
    }

    # save locally first always
    _save_to_local(entry)

    # sync to cloud via render server
    import threading
    def _sync():
        try:
            import asyncio
            from core.cloud_client import cloud_save_post
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(cloud_save_post(entry))
        except Exception:
            pass  # local save already done
    threading.Thread(target=_sync, daemon=True).start()

    return entry["id"]


def load_posts(user_id: Optional[str] = None) -> list:
    return _load_local_posts()


def verify_post(post_id: str, post_url: str = "", user_id: Optional[str] = None) -> dict:
    posts = _load_local_posts()
    found = False
    for post in posts:
        if post.get("id") == post_id:
            post["posted_verified"] = True
            post["declined"] = False
            post["posted_declined"] = False
            post["verified_at"] = datetime.now().isoformat()
            if post_url:
                post["tweet_url"] = post_url
                post["post_url"] = post_url
            found = True
            break
    if found:
        save_posts(posts)
        return {"success": True, "post_id": post_id}
    return {"success": False, "error": "post not found"}


def decline_post(post_id: str, user_id: Optional[str] = None) -> dict:
    posts = _load_local_posts()
    found = False
    for post in posts:
        if post.get("id") == post_id:
            post["declined"] = True
            post["posted_declined"] = True
            found = True
            break
    if found:
        save_posts(posts)
        return {"success": True, "post_id": post_id}
    return {"success": False, "error": "post not found"}


def get_unverified_posts(user_id: Optional[str] = None) -> list:
    posts = [
        entry for entry in load_posts(user_id)
        if not entry.get("posted_verified") and not entry.get("posted_declined") and not entry.get("declined")
    ]
    return sorted(posts, key=lambda item: item.get("timestamp", ""), reverse=True)


def get_streak(user_id: Optional[str] = None) -> dict:
    posts = [post for post in load_posts(user_id) if not post.get("posted_declined") and not post.get("declined")]
    if not posts:
        return {"current_streak": 0, "best_streak": 0, "total_posts": 0, "last_post_date": ""}

    post_dates = set()
    for entry in posts:
        try:
            post_dates.add(datetime.fromisoformat(str(entry["timestamp"]).replace("Z", "+00:00")).date())
        except (KeyError, ValueError):
            continue

    if not post_dates:
        return {"current_streak": 0, "best_streak": 0, "total_posts": len(posts), "last_post_date": ""}

    sorted_dates = sorted(post_dates, reverse=True)
    last_post_date = sorted_dates[0]
    today = datetime.now().date()
    if last_post_date < today - timedelta(days=1):
        return {
            "current_streak": 0,
            "best_streak": 0,
            "total_posts": len(posts),
            "last_post_date": str(last_post_date),
        }

    streak = 1
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i - 1] - timedelta(days=1):
            streak += 1
        else:
            break

    best_streak = 1
    running = 1
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i - 1] - timedelta(days=1):
            running += 1
        else:
            best_streak = max(best_streak, running)
            running = 1
    best_streak = max(best_streak, running)

    return {
        "current_streak": streak,
        "best_streak": best_streak,
        "total_posts": len(posts),
        "last_post_date": str(last_post_date),
    }


if __name__ == "__main__":
    print("[Logger] Storage logger module loaded")
