import json
from datetime import datetime, timedelta
from config.settings import POST_LOG


def log_post(
    post_text: str,
    format_key: str,
    screenshot_path: str,
    tweet_url: str = "",
    tweet_id: str = "",
    fallback: bool = False,
    timestamp: str = "",
) -> None:
    """Append a JSON log entry for a published post to POST_LOG (one entry per line)."""
    if not timestamp:
        timestamp = datetime.now().isoformat()

    entry = {
        "timestamp": timestamp,
        "post_text": post_text,
        "format_key": format_key,
        "screenshot_path": screenshot_path,
        "tweet_url": tweet_url,
        "tweet_id": tweet_id,
        "fallback": fallback,
    }

    try:
        with open(POST_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"[Logger] Post logged to {POST_LOG}")
    except Exception as e:
        print(f"[Logger] Failed to log post: {e}")


def load_posts() -> list:
    """Read all post entries from POST_LOG and return as a list of dicts."""
    if not POST_LOG.exists():
        return []
    entries = []
    with open(POST_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def get_streak() -> dict:
    """
    Calculate posting streak stats:
      - current_streak: consecutive days with at least one post (ending today or yesterday)
      - total_posts: total number of posts logged
      - last_post_date: date string of the most recent post
    """
    posts = load_posts()
    if not posts:
        return {"current_streak": 0, "total_posts": 0, "last_post_date": ""}

    # collect unique post dates
    post_dates = set()
    for entry in posts:
        try:
            dt = datetime.fromisoformat(entry["timestamp"])
            post_dates.add(dt.date())
        except (KeyError, ValueError):
            continue

    if not post_dates:
        return {"current_streak": 0, "total_posts": len(posts), "last_post_date": ""}

    sorted_dates = sorted(post_dates, reverse=True)
    last_post_date = sorted_dates[0]

    # streak must start from today or yesterday to count as current
    today = datetime.now().date()
    if last_post_date < today - timedelta(days=1):
        return {
            "current_streak": 0,
            "total_posts": len(posts),
            "last_post_date": str(last_post_date),
        }

    # count consecutive days backwards from the most recent post date
    streak = 1
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] == sorted_dates[i - 1] - timedelta(days=1):
            streak += 1
        else:
            break

    return {
        "current_streak": streak,
        "total_posts": len(posts),
        "last_post_date": str(last_post_date),
    }


if __name__ == "__main__":
    print("[Logger] Logging a sample post...")
    log_post(
        post_text="🚀 Just shipped a new feature! #buildinpublic",
        format_key="quick_win",
        screenshot_path="storage/data/test_screenshot.png",
        tweet_url="https://twitter.com/i/web/status/123456789",
        tweet_id="123456789",
        fallback=False,
    )
    print(f"[Logger] All posts: {load_posts()}")
    print(f"[Logger] Streak: {get_streak()}")
