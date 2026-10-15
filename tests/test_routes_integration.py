import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from api.auth import get_token
from api.server import app


class TestRoutesIntegration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, client=("127.0.0.1", 50000))

    def test_health_check_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("missing_api_keys", data)
        self.assertIn("ready", data)
        self.assertTrue(data["generation_ready"])
        self.assertIn(data["generation_mode"], {"gitcast_cloud", "byok"})
        self.assertIn("publishing_ready", data)
        self.assertIn("ocr_ready", data)

    def test_token_endpoint_localhost(self):
        response = self.client.get("/api/token")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("token", data)

    @patch("core.cloud_client.cloud_generate_article")
    def test_article_generate_endpoint_success(self, mock_cloud_article):
        mock_cloud_article.return_value = "# Technical Article Header\n\nArticle body content."

        payload = {
            "narrative": "Building a dev tool",
            "readme_content": "# Project Readme",
            "sprint_log": ["Log item 1"],
            "project_context": "Python FastAPI",
        }

        response = self.client.post("/api/article/generate", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("article"), "# Technical Article Header\n\nArticle body content.")

    @patch("core.cloud_client.cloud_generate_article")
    def test_article_generate_endpoint_failure(self, mock_cloud_article):
        mock_cloud_article.return_value = ""

        payload = {"narrative": ""}
        response = self.client.post("/api/article/generate", json=payload)
        self.assertEqual(response.status_code, 502)
        data = response.json()
        self.assertIn("Article generation failed", data.get("detail", ""))

    def test_viral_patterns_endpoint(self):
        response = self.client.get("/api/patterns")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("hot_take", data)

    @patch("api.routes.load_local_posts")
    def test_history_endpoint(self, mock_load_posts):
        mock_load_posts.return_value = [
            {
                "id": "p1",
                "post_text": "Sample history post",
                "format_key": "deep_tech",
                "timestamp": "2026-08-13T10:00:00",
            }
        ]
        response = self.client.get("/api/history")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        posts = data.get("posts") if "posts" in data else data.get("history")
        self.assertIsNotNone(posts)
        self.assertTrue(len(posts) > 0)

    @patch("api.routes.generate_posts", new_callable=AsyncMock)
    def test_generate_endpoint_uses_cloud_adapter_contract(self, mock_generate):
        mock_generate.return_value = {"quick_win": "Shipped a useful change."}
        response = self.client.post(
            "/api/generate",
            headers={"X-Session-Token": get_token()},
            json={
                "raw_thought": "I shipped a useful change.",
                "git_diff": "diff --git a/app.py b/app.py\n+def health(): pass",
                "git_diff_available": True,
                "format_keys": ["quick_win"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["variations"][0]["content"], "Shipped a useful change.")
        mock_generate.assert_awaited_once()

    @patch("ai.generator.generate_posts", new_callable=AsyncMock)
    @patch("core.ocr.run_ocr")
    @patch("core.capture.run_capture")
    def test_capture_trigger_uses_cloud_adapter_contract(
        self, mock_capture, mock_ocr, mock_generate
    ):
        mock_capture.return_value = {
            "screenshot": {"path": "storage/data/screenshots/test.png", "timestamp": "test"},
            "git_diff": {"diff": "diff --git a/app.py b/app.py\n+def health(): pass", "success": True},
            "working_dir": ".",
        }
        mock_ocr.return_value = {"text": "", "raw_text": "", "confidence": 0, "use_vision_fallback": False}
        mock_generate.return_value = {"quick_win": "Shipped a useful change."}

        with TemporaryDirectory() as directory, patch(
            "api.routes.CURRENT_DRAFT", Path(directory) / "current_draft.json"
        ):
            response = self.client.post(
                "/api/capture/trigger",
                headers={"X-Session-Token": get_token()},
                json={"delay": 0},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        mock_generate.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
