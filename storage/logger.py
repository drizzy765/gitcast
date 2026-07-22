<<<<<<< HEAD
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from storage.supabase_client import get_client


def _is_supabase_user(user_id: Optional[str]) -> bool:
    try:
        UUID(str(user_id))
        return True
    except (TypeError, ValueError):
        return False


def _normalize_entry(entry: dict) -> dict:
    timestamp = entry.get("timestamp") or entry.get("created_at") or ""
    tweet_url = entry.get("tweet_url", "") or ""
    return {
        **entry,
        "id": str(entry.get("id", "")),
        "timestamp": timestamp,
        "posted_verified": bool(entry.get("posted_verified", False)),
        "posted_declined": bool(entry.get("declined", False)),
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


def save_posts(posts: list, user_id: Optional[str] = None) -> None:
    print("[Logger] save_posts is deprecated for Supabase storage")


def log_post(
    post_text: str,
    format_key: str,
    screenshot_path: str,
    tweet_url: str = "",
    tweet_id: str = "",
    fallback: bool = False,
    timestamp: str = "",
    user_id: Optional[str] = None,
    provider_used: str = "",
) -> Optional[str]:
    if not user_id:
        raise ValueError("user_id is required")
    if not _is_supabase_user(user_id):
        print("[Logger] Local user detected; skipping Supabase post log")
        return None

    payload = {
        "user_id": user_id,
        "post_text": post_text,
        "format_key": format_key,
        "provider_used": provider_used or ("fallback" if fallback else ""),
        "platform": "twitter",
        "tweet_url": tweet_url,
        "tweet_id": tweet_id,
    }
    if timestamp:
        payload["timestamp"] = timestamp

    try:
        response = get_client().table("posts").insert(payload).execute()
        row = response.data[0] if response.data else {}
        print("[Logger] Post metadata logged to Supabase")
        return row.get("id")
    except Exception as e:
        print(f"[Logger] Failed to log post metadata: {e}")
        return None


def load_posts(user_id: str) -> list:
    if not _is_supabase_user(user_id):
        return []

    try:
        response = (
            get_client()
            .table("posts")
            .select("*")
            .eq("user_id", user_id)
            .order("timestamp", desc=True)
            .execute()
        )
        return [_normalize_entry(entry) for entry in (response.data or [])]
    except Exception as e:
        print(f"[Logger] Failed to load posts: {e}")
        return []


def verify_post(post_id: str, post_url: str = "", user_id: Optional[str] = None) -> dict:
    if not user_id:
        return {"success": False, "error": "user_id is required"}
    if not _is_supabase_user(user_id):
        return {"success": False, "error": "local history is not backed by Supabase"}

    payload = {
        "posted_verified": True,
        "declined": False,
        "verified_at": datetime.now().isoformat(),
    }
    if post_url:
        payload["tweet_url"] = post_url

    response = (
        get_client()
        .table("posts")
        .update(payload)
        .eq("id", post_id)
        .eq("user_id", user_id)
        .execute()
    )
    if response.data:
        return {"success": True, "post_id": post_id}
    return {"success": False, "error": "post not found"}


def decline_post(post_id: str, user_id: Optional[str] = None) -> dict:
    if not user_id:
        return {"success": False, "error": "user_id is required"}
    if not _is_supabase_user(user_id):
        return {"success": False, "error": "local history is not backed by Supabase"}

    response = (
        get_client()
        .table("posts")
        .update({"declined": True})
        .eq("id", post_id)
        .eq("user_id", user_id)
        .execute()
    )
    if response.data:
        return {"success": True, "post_id": post_id}
    return {"success": False, "error": "post not found"}


def get_unverified_posts(user_id: str) -> list:
    posts = [
        entry for entry in load_posts(user_id)
        if not entry.get("posted_verified") and not entry.get("posted_declined")
    ]
    return sorted(posts, key=lambda item: item.get("timestamp", ""), reverse=True)


def get_streak(user_id: str) -> dict:
    posts = [post for post in load_posts(user_id) if not post.get("posted_declined")]
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
    print("[Logger] Supabase logger module loaded")
=======
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import json

from storage.supabase_client import get_client


def _is_supabase_user(user_id: Optional[str]) -> bool:
    try:
        UUID(str(user_id))
        return True
    except (TypeError, ValueError):
        return False


def _normalize_entry(entry: dict) -> dict:
    timestamp = entry.get("timestamp") or entry.get("created_at") or ""
    tweet_url = entry.get("tweet_url", "") or ""
    return {
        **entry,
        "id": str(entry.get("id", "")),
        "timestamp": timestamp,
        "posted_verified": bool(entry.get("posted_verified", False)),
        "posted_declined": bool(entry.get("declined", False)),
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


def save_posts(posts: list, user_id: Optional[str] = None) -> None:
    from config.settings import POST_LOG

    POST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(POST_LOG, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=4)


def _save_to_local(entry: dict) -> None:
    from config.settings import POST_LOG
    from uuid import uuid4

    POST_LOG.parent.mkdir(parents=True, exist_ok=True)
    posts = []
    if POST_LOG.exists() and POST_LOG.stat().st_size:
        try:
            with open(POST_LOG, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    posts = data
        except Exception:
            posts = []

    entry = {"id": entry.get("id") or str(uuid4()), **entry}
    posts.append(entry)
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
    session_id: str = "",
    user_id: Optional[str] = None,
    provider_used: str = "",
) -> Optional[str]:
    from uuid import uuid4

    entry = {
        "id": str(uuid4()),
        "post_text": post_text,
        "format_key": format_key,
        "screenshot_path": screenshot_path,
        "tweet_url": tweet_url,
        "tweet_id": tweet_id,
        "fallback": fallback,
        "timestamp": timestamp or datetime.now().isoformat(),
        "posted_verified": False,
        "declined": False,
        "session_id": session_id or user_id or "",
        "provider_used": provider_used or ("fallback" if fallback else ""),
    }
    _save_to_local(entry)

    import asyncio
    import threading

    def _cloud_save():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            from core.cloud_client import cloud_save_post

            loop.run_until_complete(cloud_save_post(entry))
        except Exception:
            pass
        finally:
            try:
                loop.close()
            except Exception:
                pass

    threading.Thread(target=_cloud_save, daemon=True).start()
    return entry.get("id")


def load_posts(user_id: str) -> list:
    from config.settings import POST_LOG
    if not POST_LOG.exists() or POST_LOG.stat().st_size == 0:
        return []
    try:
        with open(POST_LOG, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [_normalize_entry(entry) for entry in data]
        return []
    except Exception as e:
        print(f"[Logger] Failed to load local posts: {e}")
        return []


def verify_post(post_id: str, post_url: str = "", user_id: Optional[str] = None) -> dict:
    if not user_id:
        return {"success": False, "error": "user_id is required"}
    if not _is_supabase_user(user_id):
        return {"success": False, "error": "local history is not backed by Supabase"}

    payload = {
        "posted_verified": True,
        "declined": False,
        "verified_at": datetime.now().isoformat(),
    }
    if post_url:
        payload["tweet_url"] = post_url

    response = (
        get_client()
        .table("posts")
        .update(payload)
        .eq("id", post_id)
        .eq("user_id", user_id)
        .execute()
    )
    if response.data:
        return {"success": True, "post_id": post_id}
    return {"success": False, "error": "post not found"}


def decline_post(post_id: str, user_id: Optional[str] = None) -> dict:
    if not user_id:
        return {"success": False, "error": "user_id is required"}
    if not _is_supabase_user(user_id):
        return {"success": False, "error": "local history is not backed by Supabase"}

    response = (
        get_client()
        .table("posts")
        .update({"declined": True})
        .eq("id", post_id)
        .eq("user_id", user_id)
        .execute()
    )
    if response.data:
        return {"success": True, "post_id": post_id}
    return {"success": False, "error": "post not found"}


def get_unverified_posts(user_id: str) -> list:
    posts = [
        entry for entry in load_posts(user_id)
        if not entry.get("posted_verified") and not entry.get("posted_declined")
    ]
    return sorted(posts, key=lambda item: item.get("timestamp", ""), reverse=True)


def get_streak(user_id: str) -> dict:
    posts = [post for post in load_posts(user_id) if not post.get("posted_declined")]
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
    print("[Logger] Supabase logger module loaded")
>>>>>>> 1305f09 ( docs: update README with detailed features, CLI reference, and architecture flow)
