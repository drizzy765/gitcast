from datetime import datetime
from typing import Optional

from storage.supabase_client import get_client


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
    if not user_id:
        return {"success": False, "error": "user_id is required"}

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
    response = (
        get_client()
        .table("posts")
        .update(payload)
        .eq("id", post_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not response.data:
        return {"success": False, "error": "post not found"}
    return {"success": True}


def get_all_metrics(user_id: Optional[str] = None) -> list:
    if not user_id:
        return []

    response = (
        get_client()
        .table("posts")
        .select("id,impressions,likes,comments,reposts,hashtags,platform,metrics_saved_at,days_after_post")
        .eq("user_id", user_id)
        .eq("metrics_saved", True)
        .execute()
    )
    entries = []
    for row in response.data or []:
        entries.append({
            "post_id": row["id"],
            "impressions": row.get("impressions") or 0,
            "likes": row.get("likes") or 0,
            "comments": row.get("comments") or 0,
            "reposts": row.get("reposts") or 0,
            "hashtags": row.get("hashtags") or [],
            "platform": row.get("platform") or "",
            "measured_at": row.get("metrics_saved_at") or "",
            "days_after_post": row.get("days_after_post") or 0,
        })
    return entries


def get_metrics(post_id: str, user_id: Optional[str] = None) -> dict:
    if not user_id:
        return {}

    response = (
        get_client()
        .table("posts")
        .select("id,impressions,likes,comments,reposts,hashtags,platform,metrics_saved_at,days_after_post")
        .eq("id", post_id)
        .eq("user_id", user_id)
        .eq("metrics_saved", True)
        .execute()
    )
    if not response.data:
        return {}
    row = response.data[0]
    return {
        "post_id": row["id"],
        "impressions": row.get("impressions") or 0,
        "likes": row.get("likes") or 0,
        "comments": row.get("comments") or 0,
        "reposts": row.get("reposts") or 0,
        "hashtags": row.get("hashtags") or [],
        "platform": row.get("platform") or "",
        "measured_at": row.get("metrics_saved_at") or "",
        "days_after_post": row.get("days_after_post") or 0,
    }


if __name__ == "__main__":
    print("[Metrics] Supabase metrics module loaded")
