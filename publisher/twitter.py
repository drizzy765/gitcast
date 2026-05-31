import os
import tweepy
from config.settings import (
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_SECRET,
    TWITTER_BEARER_TOKEN,
)
from publisher.clipboard import open_x_compose
from api.analytics import track


def is_configured() -> bool:
    """Return True only if all 5 Twitter API keys are present and non-empty."""
    return all([
        TWITTER_API_KEY,
        TWITTER_API_SECRET,
        TWITTER_ACCESS_TOKEN,
        TWITTER_ACCESS_SECRET,
        TWITTER_BEARER_TOKEN,
    ])


def upload_media(screenshot_path: str) -> str:
    """Upload an image via tweepy v1.1 API and return the media_id string."""
    try:
        auth = tweepy.OAuth1UserHandler(
            TWITTER_API_KEY,
            TWITTER_API_SECRET,
            TWITTER_ACCESS_TOKEN,
            TWITTER_ACCESS_SECRET,
        )
        api = tweepy.API(auth)
        media = api.media_upload(filename=screenshot_path)
        media_id = str(media.media_id)
        print(f"[Publisher] Media uploaded — media_id: {media_id}")
        return media_id
    except Exception as e:
        print(f"[Publisher] Media upload failed: {e}")
        raise


def publish_post(post_text: str, screenshot_path: str = None) -> dict:
    """
    Publish a post to X (Twitter) via API v2.
    Falls back to clipboard if keys are missing or on any error.
    """
    if not is_configured():
        print("[Publisher] Twitter API not configured — falling back to clipboard.")
        result = open_x_compose(post_text)
        result["fallback"] = True
        track("post_published", {"platform": "twitter", "used_fallback": True})
        return result

    try:
        client = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
        )

        media_ids = None
        if screenshot_path and os.path.exists(screenshot_path):
            try:
                media_id = upload_media(screenshot_path)
                media_ids = [media_id]
            except Exception as e:
                print(f"[Publisher] Skipping media attachment: {e}")

        response = client.create_tweet(text=post_text, media_ids=media_ids)
        tweet_id = str(response.data["id"])
        tweet_url = f"https://twitter.com/i/web/status/{tweet_id}"

        print(f"[Publisher] Tweet posted — {tweet_url}")
        track("post_published", {"platform": "twitter", "used_fallback": False})
        return {
            "success": True,
            "tweet_url": tweet_url,
            "tweet_id": tweet_id,
            "fallback": False,
        }

    except Exception as e:
        print(f"[Publisher] Twitter API error: {e}")
        print("[Publisher] Falling back to clipboard.")
        result = open_x_compose(post_text)
        result["fallback"] = True
        track("post_published", {"platform": "twitter", "used_fallback": True})
        return result


if __name__ == "__main__":
    print(f"[Publisher] Twitter configured: {is_configured()}")
    if is_configured():
        print("[Publisher] All 5 API keys are present.")
    else:
        print("[Publisher] Missing one or more Twitter API keys — clipboard fallback will be used.")
