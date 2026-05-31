from collections import defaultdict
from datetime import datetime, timedelta

from storage.logger import get_streak, load_posts
from storage.metrics import get_all_metrics


def _parse_dt(value: str):
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _avg(values: list) -> float:
    return sum(values) / len(values) if values else 0.0


def _engagement_rate(metrics: dict) -> float:
    impressions = max(0, int(metrics.get("impressions", 0)))
    if impressions == 0:
        return 0.0
    engagement = int(metrics.get("likes", 0)) + int(metrics.get("comments", 0)) + int(metrics.get("reposts", 0))
    return round((engagement / impressions) * 100, 2)


def _bucket_chars(count: int) -> str:
    if count <= 140:
        return "0-140"
    if count <= 200:
        return "141-200"
    if count <= 260:
        return "201-260"
    return "261-280"


def _time_window(dt: datetime) -> str:
    hour = dt.hour
    if 6 <= hour < 9:
        return "6am-9am"
    if 9 <= hour < 12:
        return "9am-12pm"
    if 12 <= hour < 15:
        return "12pm-3pm"
    if 15 <= hour < 18:
        return "3pm-6pm"
    if 18 <= hour < 21:
        return "6pm-9pm"
    if 21 <= hour < 23:
        return "9pm-11pm"
    return "late-night"


def _best_group(rows: list, key: str) -> dict:
    groups = defaultdict(list)
    for row in rows:
        if row.get(key):
            groups[row[key]].append(row["impressions"])
    if not groups:
        return {}
    name, values = max(groups.items(), key=lambda item: _avg(item[1]))
    return {"name": name, "avg": round(_avg(values), 1), "sample_size": len(values)}


def calculate_insights() -> dict:
    posts = load_posts()
    metrics_entries = get_all_metrics()
    metrics_by_post = {}
    for metric in metrics_entries:
        metrics_by_post[metric.get("post_id")] = metric

    rows = []
    for post in posts:
        post_id = post.get("id") or post.get("timestamp")
        metrics = metrics_by_post.get(post_id) or post.get("metrics")
        if not metrics:
            continue
        dt = _parse_dt(post.get("timestamp", ""))
        impressions = int(metrics.get("impressions", 0))
        row = {
            "post_id": post_id,
            "post_text": post.get("post_text", ""),
            "format_key": post.get("format_key", ""),
            "timestamp": post.get("timestamp", ""),
            "dt": dt,
            "day": dt.strftime("%A").lower() if dt else "",
            "time_window": _time_window(dt) if dt else "",
            "char_bucket": _bucket_chars(len(post.get("post_text", ""))),
            "impressions": impressions,
            "likes": int(metrics.get("likes", 0)),
            "comments": int(metrics.get("comments", 0)),
            "reposts": int(metrics.get("reposts", 0)),
            "hashtags": metrics.get("hashtags", []),
            "engagement_rate": _engagement_rate(metrics),
        }
        rows.append(row)

    if len(rows) < 5:
        return {"insufficient_data": True, "posts_needed": 5 - len(rows), "posts_with_metrics": len(rows)}

    cutoff = datetime.now() - timedelta(days=30)
    recent = [row for row in rows if row["dt"] and row["dt"] >= cutoff] or rows
    streak = get_streak()
    total_impressions = sum(row["impressions"] for row in recent)
    best_format = _best_group(rows, "format_key")
    best_day = _best_group(rows, "day")
    best_time = _best_group(rows, "time_window")
    top = max(rows, key=lambda row: row["impressions"])
    overall_avg = _avg([row["impressions"] for row in rows])

    patterns = []
    by_format = defaultdict(list)
    by_chars = defaultdict(list)
    by_day = defaultdict(list)
    tags = defaultdict(list)
    for row in rows:
        by_format[row["format_key"]].append(row["impressions"])
        by_chars[row["char_bucket"]].append(row["impressions"])
        by_day[row["day"]].append(row["impressions"])
        for tag in row["hashtags"]:
            tags[tag].append(row["impressions"])

    if len(by_format) >= 2:
        ordered = sorted(by_format.items(), key=lambda item: _avg(item[1]), reverse=True)
        high, low = ordered[0], ordered[-1]
        if _avg(low[1]) > 0:
            patterns.append({
                "pattern": "format",
                "description": f"{high[0].upper()} format gets {round(_avg(high[1]) / _avg(low[1]), 1)}x more impressions than {low[0].upper()}",
                "impact": "high",
            })
    if by_chars:
        bucket, values = max(by_chars.items(), key=lambda item: _avg(item[1]))
        lift = round(((_avg(values) - overall_avg) / overall_avg) * 100, 0) if overall_avg else 0
        patterns.append({"pattern": "length", "description": f"posts in the {bucket} char bucket get {lift}% more engagement", "impact": "medium"})
    if by_day:
        day, values = max(by_day.items(), key=lambda item: _avg(item[1]))
        multiple = round(_avg(values) / overall_avg, 1) if overall_avg else 0
        patterns.append({"pattern": "day", "description": f"{day} posts get {multiple}x your average", "impact": "medium"})

    hashtag_performance = [
        {"hashtag": tag, "avg_impressions": round(_avg(values), 1), "uses": len(values)}
        for tag, values in sorted(tags.items(), key=lambda item: _avg(item[1]), reverse=True)
    ]
    for tag in hashtag_performance[:3]:
        patterns.append({
            "pattern": "hashtag",
            "description": f"{tag['hashtag']} adds avg {int(tag['avg_impressions'])} impressions",
            "impact": "medium",
        })

    return {
        "overview": {
            "total_posts": len(recent),
            "total_verified": len([post for post in posts if post.get("posted_verified")]),
            "total_impressions": total_impressions,
            "avg_engagement_rate": round(_avg([row["engagement_rate"] for row in recent]), 2),
            "posting_streak": streak.get("current_streak", 0),
            "best_streak": streak.get("best_streak", streak.get("current_streak", 0)),
        },
        "best_format": {"format_key": best_format.get("name", ""), "avg_impressions": best_format.get("avg", 0.0), "sample_size": best_format.get("sample_size", 0)},
        "best_day": {"day": best_day.get("name", ""), "avg_impressions": best_day.get("avg", 0.0)},
        "best_time": {"window": best_time.get("name", ""), "avg_impressions": best_time.get("avg", 0.0)},
        "top_post": {key: top[key] for key in ["post_text", "impressions", "likes", "format_key", "timestamp"]},
        "viral_patterns": patterns[:8],
        "hashtag_performance": hashtag_performance[:20],
    }


if __name__ == "__main__":
    print("[Insights] Calculated insights:", calculate_insights())
