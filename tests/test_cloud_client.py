import unittest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

import httpx

from core.cloud_client import (
    get_headers,
    cloud_generate,
    cloud_refine,
    cloud_save_post,
    cloud_get_posts,
    cloud_generate_article,
    check_server_health,
)


class TestCloudClient(unittest.TestCase):
    @patch("core.cloud_client._byok_key", return_value="test-key-123")
    @patch("core.cloud_client._byok_provider", return_value="groq")
    def test_get_headers_with_byok(self, mock_provider, mock_key):
        headers = get_headers()
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["X-BYOK-Key"], "test-key-123")
        self.assertEqual(headers["X-BYOK-Provider"], "groq")

    @patch("core.cloud_client._byok_key", return_value="")
    def test_get_headers_without_byok(self, mock_key):
        headers = get_headers()
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertNotIn("X-BYOK-Key", headers)

    @patch("httpx.AsyncClient.post")
    def test_cloud_generate_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "variations": {
                "deep_tech": "Just built a custom logging pipeline!",
                "linkedin": "Excited to share our latest architecture update...",
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        payload = {"raw_thought": "Built custom logging pipeline"}
        res = asyncio.run(cloud_generate(payload))

        self.assertIn("deep_tech", res)
        self.assertIn("linkedin", res)
        self.assertEqual(res["deep_tech"], "Just built a custom logging pipeline!")

    @patch("httpx.AsyncClient.post")
    def test_cloud_refine_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "refined_post": "Refined: Just built a high-performance logging pipeline!"
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        refined = asyncio.run(
            cloud_refine(
                current_post="Just built a logging pipeline",
                instruction="Make it more impactful",
                format_key="deep_tech",
            )
        )
        self.assertEqual(
            refined, "Refined: Just built a high-performance logging pipeline!"
        )

    @patch("httpx.AsyncClient.post")
    def test_cloud_generate_article_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "article": "# Deep Dive into Gitcast Architecture\n\nGitcast automates build logs..."
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        payload = {
            "narrative": "Building automated developer tool",
            "readme_content": "# Gitcast\nAutomated dev post generator",
            "sprint_log": ["Fixed bugs", "Added cloud client"],
            "project_context": "Python package",
        }
        article = asyncio.run(cloud_generate_article(payload))
        self.assertTrue(article.startswith("# Deep Dive"))

    @patch("httpx.AsyncClient.post")
    def test_cloud_generate_article_400_handling(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request: Missing required field"
        mock_post.return_value = mock_response

        payload = {"invalid_field": "test"}
        article = asyncio.run(cloud_generate_article(payload))
        self.assertEqual(article, "")

    @patch("httpx.get")
    def test_check_server_health_ok(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "ok",
            "ready": True,
        }
        mock_get.return_value = mock_response

        health = check_server_health()
        self.assertEqual(health["status"], "ok")
        self.assertTrue(health["ready"])

    @patch("httpx.get", side_effect=Exception("Connection refused"))
    def test_check_server_health_unreachable(self, mock_get):
        health = check_server_health()
        self.assertEqual(health["status"], "unreachable")


if __name__ == "__main__":
    unittest.main()
