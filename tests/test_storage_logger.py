import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from storage.logger import (
    _normalize_entry,
    _load_local_posts,
    log_post,
    get_streak,
)


class TestStorageLogger(unittest.TestCase):
    def test_normalize_entry_basic(self):
        raw_entry = {
            "id": "post-123",
            "post_text": "Building a new feature for Gitcast!",
            "format_key": "deep_tech",
            "timestamp": "2026-08-13T18:00:00",
            "posted_verified": True,
            "declined": False,
            "tweet_url": "https://x.com/user/status/123456789",
            "metrics_saved": True,
            "impressions": 1500,
            "likes": 45,
            "comments": 12,
            "reposts": 8,
            "hashtags": ["#buildinpublic", "#python"],
            "platform": "twitter",
            "days_after_post": 1,
            "metrics_saved_at": "2026-08-14T18:00:00",
        }
        normalized = _normalize_entry(raw_entry)
        self.assertEqual(normalized["id"], "post-123")
        self.assertEqual(normalized["post_url"], "https://x.com/user/status/123456789")
        self.assertTrue(normalized["posted_verified"])
        self.assertFalse(normalized["posted_declined"])
        self.assertEqual(normalized["metrics"]["impressions"], 1500)

    def test_normalize_entry_empty_metrics(self):
        raw_entry = {
            "id": "post-456",
            "post_text": "Minimal test entry",
            "format_key": "linkedin",
            "timestamp": "2026-08-13T19:00:00",
            "posted_verified": False,
            "declined": True,
        }
        normalized = _normalize_entry(raw_entry)
        self.assertEqual(normalized["id"], "post-456")
        self.assertFalse(normalized["posted_verified"])
        self.assertTrue(normalized["posted_declined"])
        self.assertEqual(normalized["metrics"], {})

    @patch("config.settings.POST_LOG")
    def test_save_and_load_local_posts(self, mock_post_log):
        mock_post_log.exists.return_value = True
        mock_post_log.stat.return_value.st_size = 100

        sample_posts = [
            {
                "id": "1",
                "post_text": "First post",
                "format_key": "deep_tech",
                "timestamp": "2026-08-10T12:00:00",
            },
            {
                "id": "2",
                "post_text": "Second post",
                "format_key": "linkedin",
                "timestamp": "2026-08-11T12:00:00",
            },
        ]

        m = unittest.mock.mock_open(read_data=json.dumps(sample_posts))
        with patch("builtins.open", m):
            loaded = _load_local_posts()
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0]["id"], "1")
            self.assertEqual(loaded[1]["id"], "2")

    @patch("storage.logger._save_to_local")
    @patch("core.cloud_client.cloud_save_post")
    def test_log_post_execution(self, mock_cloud_save, mock_save_local):
        post_id = log_post(
            post_text="New feature launched!",
            format_key="deep_tech",
            screenshot_path="/path/to/shot.png",
            tweet_url="https://x.com/status/100",
            tweet_id="100",
            fallback=False,
            user_id="dev_user",
            provider_used="groq",
        )
        self.assertIsNotNone(post_id)
        mock_save_local.assert_called_once()

    def test_streak_calculation_empty(self):
        with patch("storage.logger.load_posts", return_value=[]):
            streak = get_streak("local")
            self.assertEqual(streak["current_streak"], 0)
            self.assertEqual(streak["best_streak"], 0)
            self.assertEqual(streak["total_posts"], 0)

    def test_streak_calculation_active(self):
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        posts = [
            {"timestamp": f"{today.isoformat()}T10:00:00", "posted_declined": False},
            {"timestamp": f"{yesterday.isoformat()}T10:00:00", "posted_declined": False},
            {"timestamp": f"{two_days_ago.isoformat()}T10:00:00", "posted_declined": False},
        ]

        with patch("storage.logger.load_posts", return_value=posts):
            streak = get_streak("local")
            self.assertEqual(streak["current_streak"], 3)
            self.assertEqual(streak["best_streak"], 3)
            self.assertEqual(streak["total_posts"], 3)


if __name__ == "__main__":
    unittest.main()
