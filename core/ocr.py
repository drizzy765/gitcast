import os
import pytesseract
from PIL import Image
from pathlib import Path
from config.settings import get_ocr_threshold
from core.log_stream import stream_log

# ── Tesseract path (Windows) ──────────────────────────────────────────────────

# explicitly set the tesseract path for Windows
# if installed elsewhere, update this path
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if Path(TESSERACT_PATH).exists():
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    # fallback — rely on PATH
    stream_log("OCR", "WARN", "Tesseract not found at default path. Relying on PATH.")


# ── OCR runner ────────────────────────────────────────────────────────────────

def run_ocr(image_path: str) -> dict:
    """
    Runs Tesseract OCR on the given image.
    Returns extracted text, confidence score, and a flag indicating
    whether the result is reliable enough to send to the AI.

    If confidence is below threshold, the caller should send the
    raw screenshot to the Gemini vision endpoint instead.
    """
    threshold = get_ocr_threshold()  # default 60, set in config/settings.py

    try:
        from config.settings import BASE_DIR
        path = Path(image_path)
        if not path.is_absolute():
            path = BASE_DIR / path
        img = Image.open(path)

        # get detailed output including confidence scores per word
        data = pytesseract.image_to_data(
            img,
            output_type=pytesseract.Output.DICT,
            config="--psm 6"  # assume uniform block of text — best for code/IDE
        )

        # calculate mean confidence from words that were actually detected
        confidences = [
            int(c) for c in data["conf"]
            if str(c).strip() != "-1" and str(c).strip() != ""
        ]

        if not confidences:
            stream_log("OCR", "WARN", "confidence low (0%); no text detected")
            return _low_confidence_result("No text detected in screenshot")

        mean_confidence = sum(confidences) / len(confidences)

        # extract clean text — filter out empty strings
        raw_text = pytesseract.image_to_string(
            img,
            config="--psm 6"
        )
        filtered_text = filter_browser_chrome(raw_text)
        clean_text = _clean_ocr_text(filtered_text)

        is_reliable = mean_confidence >= threshold

        level = "OK" if is_reliable else "WARN"
        message = (
            f"confidence {mean_confidence:.1f}%"
            if is_reliable
            else f"confidence low ({mean_confidence:.1f}%) - vision fallback"
        )
        stream_log("OCR", level, message)

        return {
            "success": True,
            "text": clean_text if is_reliable else "",
            "raw_text": clean_text,
            "confidence": round(mean_confidence, 1),
            "reliable": is_reliable,
            "use_vision_fallback": not is_reliable,
            "error": "",
        }

    except FileNotFoundError:
        return _error_result(f"Screenshot file not found: {image_path}")
    except pytesseract.TesseractNotFoundError:
        return _error_result(
            "Tesseract executable not found. "
            "Install from https://github.com/UB-Mannheim/tesseract/wiki"
        )
    except Exception as e:
        return _error_result(str(e))


def filter_browser_chrome(text: str) -> str:
    """
    Removes common browser UI noise from OCR text:
    tab titles, bookmark bars, extension icons,
    single-character garbage from icons.
    """
    import re

    lines = text.split('\n')
    cleaned = []

    noise_patterns = [
        r'^\W{1,3}$',           # lines of just symbols
        r'^[a-z]{1,2}$',        # 1-2 char garbage
        r'bookmark',
        r'localhost:\d+',
        r'^\d+:\d+\s*(AM|PM)?$', # clock/time
        r'gmail|youtube|maps$',  # bookmark bar entries
        r'ask\s*(gemini|chatgpt|claude)',
        r'^[●○✓✗→←↑↓]+$',
    ]

    for line in lines:
        stripped = line.strip()
        if len(stripped) < 3:
            continue
        if any(re.search(p, stripped, re.IGNORECASE)
               for p in noise_patterns):
            continue
        # skip lines that are mostly symbols/garbage
        alpha_ratio = sum(c.isalpha() for c in stripped) / \
            max(len(stripped), 1)
        if alpha_ratio < 0.5:
            continue
        cleaned.append(stripped)

    return '\n'.join(cleaned)



# ── Text cleaning ─────────────────────────────────────────────────────────────

def _clean_ocr_text(raw: str) -> str:
    """
    Cleans raw Tesseract output for use in AI prompts.
    Removes excessive whitespace and blank lines while
    preserving code indentation structure.
    """
    lines = raw.splitlines()

    # remove completely empty lines that are repeated
    cleaned = []
    prev_empty = False
    for line in lines:
        is_empty = line.strip() == ""
        if is_empty and prev_empty:
            continue  # skip consecutive blank lines
        cleaned.append(line)
        prev_empty = is_empty

    result = "\n".join(cleaned).strip()

    # cap at 2000 chars to stay within token budget
    if len(result) > 2000:
        result = result[:2000] + "\n... [truncated]"

    return result


# ── Result helpers ────────────────────────────────────────────────────────────

def _low_confidence_result(reason: str) -> dict:
    return {
        "success": True,
        "text": "",
        "raw_text": "",
        "confidence": 0.0,
        "reliable": False,
        "use_vision_fallback": True,
        "error": reason,
    }


def _error_result(error: str) -> dict:
    stream_log("OCR", "ERROR", error)
    return {
        "success": False,
        "text": "",
        "raw_text": "",
        "confidence": 0.0,
        "reliable": False,
        "use_vision_fallback": True,
        "error": error,
    }


# ── Test ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from core.capture import capture_active_window

    print("[OCR] Taking a fresh screenshot to test on...")
    screenshot = capture_active_window()

    if not screenshot["path"]:
        print("[OCR] Screenshot failed — cannot test OCR")
        sys.exit(1)

    print(f"[OCR] Running OCR on: {screenshot['path']}")
    result = run_ocr(screenshot["path"])

    print("\n=== OCR RESULT ===")
    print(f"Success:           {result['success']}")
    print(f"Confidence:        {result['confidence']}%")
    print(f"Reliable:          {result['reliable']}")
    print(f"Use vision fallback: {result['use_vision_fallback']}")
    print(f"Error:             {result['error'] or 'none'}")
    print(f"\nExtracted text preview:")
    print(result['raw_text'][:500] if result['raw_text'] else "(none)")
