import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.payload import build_payload
from ai.generator import generate_article

def test_ocr_text_in_payload():
    print("Testing ocr_text in build_payload...")
    ocr_result = {"text": "Detected Text", "confidence": 0.9}
    capture_result = {
        "screenshot": {"path": "test.png", "timestamp": "123"},
        "git_diff": {"diff": "some diff", "success": True}
    }
    
    payload = build_payload(
        raw_thought="my thought",
        ocr_result=ocr_result,
        capture_result=capture_result
    )
    
    assert "ocr_text" in payload
    assert payload["ocr_text"] == "Detected Text"
    print("✅ build_payload includes ocr_text")

def test_generate_article_robustness():
    payload = {"git_diff": "diff --git a/app.py b/app.py"}
    with patch("core.cloud_client.cloud_generate_article", new_callable=AsyncMock) as mock_cloud:
        mock_cloud.return_value = "# Article"
        article = asyncio.run(generate_article(payload))

    assert article == "# Article"
    mock_cloud.assert_awaited_once()

if __name__ == "__main__":
    test_ocr_text_in_payload()
    test_generate_article_robustness()
