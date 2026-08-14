import unittest
import json
from unittest.mock import patch
from fastapi.testclient import TestClient

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


if __name__ == "__main__":
    unittest.main()
