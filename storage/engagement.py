import json
import time
import threading
from pathlib import Path
import tweepy
from config.settings import ENGAGEMENT_LOG, TWITTER_BEARER_TOKEN, POST_LOG
from storage.tone_memory import update_engagement

# [Engagement] module for tracking X metrics 24h after publish

def log_pending_fetch(tweet_id: str, post_text: str):
    """Saves a tweet ID to ENGAGEMENT_LOG for background processing."""
    entry = {
        "tweet_id": tweet_id,
        "post_text": post_text,
        "publish_timestamp": time.time(),
        "fetched": False
    }
    try:
        with open(ENGAGEMENT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"[Engagement] Logged pending fetch for tweet {tweet_id}")
    except Exception as e:
        print(f"[Engagement] Error logging pending fetch: {e}")

def get_pending_fetches():
    """Returns list of entries due for metrics fetch (24h+ old, not fetched)."""
    if not ENGAGEMENT_LOG.exists():
        return []
    
    pending = []
    now = time.time()
    try:
        with open(ENGAGEMENT_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                entry = json.loads(line)
                # 24 hours = 86400 seconds
                if not entry.get("fetched") and (now - entry["publish_timestamp"] > 86400):
                    pending.append(entry)
    except Exception as e:
        print(f"[Engagement] Error reading pending fetches: {e}")
    
    return pending

def fetch_and_store_metrics(tweet_id: str, post_text: str):
    """Calls X API v2 to get metrics and updates tone_memory."""
    if not TWITTER_BEARER_TOKEN:
        print("[Engagement] No Twitter Bearer Token found, skipping fetch.")
        return False

    try:
        client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
        response = client.get_tweet(tweet_id, tweet_fields=["public_metrics"])
        
        if response.data:
            metrics = response.data.public_metrics
            likes = metrics.get("like_count", 0)
            retweets = metrics.get("retweet_count", 0)
            replies = metrics.get("reply_count", 0)
            
            update_engagement(post_text, likes, retweets, replies)
            return True
        else:
            print(f"[Engagement] Could not find tweet {tweet_id}")
            return False
    except Exception as e:
        print(f"[Engagement] X API error for {tweet_id}: {e}")
        return False

def mark_as_fetched(tweet_id: str):
    """Updates ENGAGEMENT_LOG to mark a tweet as fetched."""
    if not ENGAGEMENT_LOG.exists():
        return
    
    entries = []
    try:
        with open(ENGAGEMENT_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                entry = json.loads(line)
                if entry["tweet_id"] == tweet_id:
                    entry["fetched"] = True
                entries.append(entry)
        
        with open(ENGAGEMENT_LOG, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
    except Exception as e:
        print(f"[Engagement] Error marking as fetched: {e}")

def run_engagement_worker():
    """Background thread that runs hourly and processes pending fetches."""
    def worker():
        while True:
            print("[Engagement] Checking for pending metrics fetches...")
            pending = get_pending_fetches()
            for entry in pending:
                success = fetch_and_store_metrics(entry["tweet_id"], entry["post_text"])
                if success:
                    mark_as_fetched(entry["tweet_id"])
            
            # Sleep for 1 hour
            time.sleep(3600)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    print("[Engagement] Background worker started.")

if __name__ == "__main__":
    print("=== ENGAGEMENT TRACKING TEST ===")
    log_pending_fetch("123456789", "Test post text")
    print(f"Pending: {get_pending_fetches()}")
    # Note: X API call will fail without real token in test
