# Quick Start

Get Gitcast running in under 5 minutes.

## Prerequisites

- Python 3.10 or higher
- Git installed
- Windows 10/11, macOS, or Linux
- At least one free API key (see step 2)

## Step 1 — Clone and install

```bash
git clone https://github.com/drizzy765/gitcast.git
cd gitcast
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux  
source venv/bin/activate

pip install -r requirements.txt
```

## Step 2 — Install Tesseract OCR

Tesseract is required for local text extraction from screenshots. It never sends data externally.

**Windows:**
1. Download from https://github.com/UB-Mannheim/tesseract/wiki
2. Install to `C:\Program Files\Tesseract-OCR`
3. Add to PATH: `C:\Program Files\Tesseract-OCR`

**macOS:**
```bash
brew install tesseract
```

**Linux:**
```bash
sudo apt install tesseract-ocr
```

## Step 3 — Get your free API keys

You need at least one provider key. Groq is recommended as your first key — free and takes 2 minutes.

| Provider | URL | Free Tier | Best For |
|----------|-----|-----------|----------|
| Groq | console.groq.com | 12k TPM | Quick posts |
| DeepSeek | platform.deepseek.com | $5 credit | Technical posts |
| Gemini | aistudio.google.com | 1M tokens/day | Vision fallback |
| Kimi | platform.moonshot.cn | 15 RPM | Articles |

## Step 4 — Configure environment

```bash
cp .env.example .env
```

Open `.env` and add your keys:

```ini
GROQ_API_KEY=your_groq_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here
GEMINI_API_KEY=your_gemini_key_here
```

## Step 5 — Run Gitcast

```bash
python main.py
```

Dashboard opens automatically at http://127.0.0.1:8000

Press Ctrl+Shift+P from anywhere to capture your first win.
