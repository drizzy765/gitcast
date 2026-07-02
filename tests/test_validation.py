import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.payload import validate_payload

def test_validation():
    # Test 1 — thin context (should BLOCK)
    payload_thin = {
        "raw_thought": "Captured via hotkey trigger",
        "ocr_text": "noisy ocr text", # length < 80
        "git_diff": "",
        "git_diff_available": False
    }
    is_valid, warnings = validate_payload(payload_thin)
    print("Thin context result:", is_valid, warnings)
    assert not is_valid
    assert len(warnings) == 1
    assert "Not enough context" in warnings[0]

    # Test 2 — real context (should GENERATE)
    payload_real = {
        "raw_thought": "fixed score not resetting on game over",
        "ocr_text": "game snake over score resetting",
        "git_diff": "diff --git a/snake.py b/snake.py\n+score = 0",
        "git_diff_available": True
    }
    is_valid, warnings = validate_payload(payload_real)
    print("Real context result:", is_valid, warnings)
    assert is_valid
    assert not warnings or "Not enough context" not in warnings[0]

    # Test 3 - real thought but missing diff (should WARN but allow)
    payload_warn = {
        "raw_thought": "fixed score not resetting on game over",
        "ocr_text": "game snake over score resetting",
        "git_diff": "",
        "git_diff_available": False
    }
    is_valid, warnings = validate_payload(payload_warn)
    print("Warn context result:", is_valid, warnings)
    assert is_valid
    assert any("No git diff" in w for w in warnings)

    print("✅ All validation tests passed!")

if __name__ == "__main__":
    test_validation()
