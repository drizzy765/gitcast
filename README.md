# Gitcast

On-demand, privacy-first desktop utility that captures active window context,
extracts code changes, and generates platform-ready X (Twitter) posts with one keystroke.

## Install

```bash
pip install gitcast
```

## Setup

1. Install Tesseract OCR:
   - Windows: https://github.com/UB-Mannheim/tesseract/wiki
   - Mac: `brew install tesseract`
   - Linux: `sudo apt install tesseract-ocr`

2. Add your API keys:
   ```bash
   gitcast --setup
   ```
   (opens `.env` file for editing)

3. Run:
   ```bash
   gitcast
   ```

Dashboard opens at http://127.0.0.1:8000
Press Ctrl+Shift+P from anywhere to capture.

## Stack
- Python 3.11+
- FastAPI, pynput, mss, Tesseract, Groq API, Tweepy
