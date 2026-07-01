import json
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.payload import build_payload
from api.routes import generate_article, ArticleGenerateRequest
from config.settings import CURRENT_DRAFT
from fastapi import HTTPException

async def test_ocr_text_in_payload():
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

async def test_generate_article_robustness():
    print("Testing generate_article robustness with missing ocr_text in draft...")
    original_draft = CURRENT_DRAFT.read_text(encoding="utf-8") if CURRENT_DRAFT.exists() else None
    # Mock CURRENT_DRAFT
    draft_data = {
        "payload": {
            "user_message": "hello",
            # "ocr_text" is missing
            "git_diff": "diff"
        },
        "variations": {},
        "timestamp": "123",
        "status": "ready"
    }
    
    try:
        with open(CURRENT_DRAFT, "w", encoding="utf-8") as f:
            json.dump(draft_data, f)

        request = ArticleGenerateRequest(include_codebase=False)

        try:
            # This will still try to call AI, but we want to see if it passes the user_msg construction
            # We can't easily mock the AI call here without more setup,
            # but the KeyError would happen BEFORE the AI call.

            # To avoid actual AI call, we might just check the logic in routes.py
            # by calling the function and expecting it to fail at AI call but NOT with KeyError.
            await generate_article(request)
        except HTTPException as e:
            if "Article generation failed" in e.detail:
                print("✅ generate_article passed KeyError (failed at AI call as expected)")
            else:
                print(f"❌ generate_article failed with: {e.detail}")
        except KeyError as e:
            print(f"❌ generate_article still has KeyError: {e}")
        except Exception as e:
            print(f"✅ generate_article passed KeyError (failed with: {e})")
    finally:
        if original_draft is None:
            CURRENT_DRAFT.unlink(missing_ok=True)
        else:
            CURRENT_DRAFT.write_text(original_draft, encoding="utf-8")

if __name__ == "__main__":
    asyncio.run(test_ocr_text_in_payload())
    asyncio.run(test_generate_article_robustness())
