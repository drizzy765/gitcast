# Gitcast

> **git diff → published post. under 60 seconds.**

[![PyPI version](https://img.shields.io/pypi/v/gitcast.svg)](https://pypi.org/project/gitcast/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Gitcast is a privacy-first developer tool that captures your coding session via a global hotkey, reads your local `git diff` and project context, generates AI-powered social media posts, PR descriptions, and articles, and publishes them without breaking your flow.

Works immediately after installation with zero setup required — Gitcast comes with a built-in shared key.

---

## Features

- **Global Hotkey Capture**: Press **`Ctrl+Shift+P`** or **`Ctrl+Alt+S`** anywhere (VS Code, terminal, browser) to instantly capture your screen and local code changes (`git diff`).
- **Privacy-First & Local OCR**: Screen text extraction (Tesseract OCR) runs 100% locally on your machine. Sensitive credentials (API keys, secrets, tokens, passwords) are automatically detected and blocked.
- **Automated macOS Window Framing**: Raw screenshots are automatically wrapped in a sleek macOS-style window frame with traffic light controls and soft drop shadows for social posts.
- **Multi-Format AI Generation**: Generates distinct content formats simultaneously in under 8 seconds:
  - **X (Twitter) Post**: High-impact, tech-focused updates with code context.
  - **LinkedIn Draft**: Structured narrative posts tailored for developer networks.
  - **PR Description**: Full GitHub/GitLab markdown pull request descriptions (What, Why, How, Testing).
  - **Quick Win**: Short punchy updates ideal for feature ships.
  - **Longform Article**: Medium/Substack-ready markdown blog posts.
- **Sprint Mode (Deep Work)**: Silently log multiple code captures throughout a long coding session without popups, then synthesize them into a cohesive multi-step "sprint thread" at the end.
- **Smart Vision AI Fallback**: If local OCR confidence falls below 60%, Gitcast seamlessly routes the screenshot to Gemini Vision for high-accuracy multimodal reading.
- **Interactive Local Dashboard & Review Room**: Web UI running locally at `http://localhost:8000` with live preview, inline editing, and natural language AI refinement chat.
- **1-Click Publishing & Clipboard Integration**: Publish directly to X (Twitter) via API v2 with media upload support, or copy pre-formatted markdown to clipboard.
- **Bring Your Own Key (BYOK)**: Zero setup required out-of-the-box, plus optional BYOK support for Groq, Gemini, DeepSeek, OpenRouter, and Moonshot/Kimi.

---

## Quick Start

### Step 1: Install Tesseract OCR

Required for local screenshot text extraction. Runs entirely on your device — your code never leaves your computer without permission.

- **macOS:**
  ```bash
  brew install tesseract
  ```

- **Linux (Ubuntu/Debian):**
  ```bash
  sudo apt install tesseract-ocr
  ```

- **Windows:**
  1. Download installer from [UB-Mannheim Tesseract Wiki](https://github.com/UB-Mannheim/tesseract/wiki).
  2. Run installer and check **"Add to PATH"** during installation.
  3. Restart your terminal.

### Step 2: Install Gitcast

```bash
pip install gitcast
```

### Step 3: Launch

```bash
gitcast
```

The web dashboard opens automatically at `http://localhost:8000`.

- Press **`Ctrl+Shift+P`** or **`Ctrl+Alt+S`** from any application to capture screen context and generate your post.
- Or trigger a quick capture directly from your terminal:
  ```bash
  gitcast "just added instant fallback routing for AI models"
  ```

### Step 4: Optional: Add Your Own Key (BYOK)

The built-in shared key has rate limits shared across users. For unlimited personal usage, add your own free key:

```bash
gitcast --setup
```

Or configure keys in the dashboard sidebar under **BYOK**. Get a free Groq key in 2 minutes at [console.groq.com](https://console.groq.com).

---

## Architecture & Flow

```text
  [HotKey / CLI Trigger]  ──> Press Ctrl+Shift+P or run `gitcast "thought"`
           │
           ▼
  [Local Parallel Capture] ──> Capture active screen (mss) + git diff HEAD + project README & stack
           │
           ▼
  [Privacy & OCR Engine]  ──> Tesseract OCR (Local) ──> Scan & block API keys/secrets
           │                                            (If confidence < 60% ──> Gemini Vision)
           ▼
  [AI Provider Routing]   ──> Multi-format parallel completions (Groq / Gemini / OpenRouter)
           │
           ▼
  [Dashboard & Review]    ──> http://localhost:8000 (Inline edit, AI refinement, macOS window framing)
           │
           ▼
  [Publish / Export]      ──> 1-Click X/Twitter API Publish OR Copy to Clipboard
```

### Context Awareness
Gitcast automatically detects project context from your current working directory:
- Reads `README.md` for project background.
- Scans `package.json`, `requirements.txt`, `Cargo.toml`, `go.mod`, etc., for main tech stack & language.
- Remembers your **Project Narrative** (e.g., *"Building an open-source observability engine"*), ensuring every generated post sounds authentic to what you are creating.

---

## Sprint Mode

For deep work sessions where you do not want to break your flow:

1. **Activate Sprint Mode**: Toggle **Sprint Mode** `[ON]` from the dashboard sidebar or tray icon.
2. **Capture Silently**: Every `Ctrl+Shift+P` press logs your screenshot and `git diff` silently in the background without popups or AI calls.
3. **Finish & Synthesize**: Toggle Sprint Mode `[OFF]`. Gitcast synthesizes all logged captures into a single, high-converting 6–7 tweet "sprint thread" covering your entire build arc (the problem, failed attempts, solution, and outcome).

---

## CLI Reference

| Command | Description |
|---|---|
| `gitcast` | Start dashboard server (`http://localhost:8000`), global hotkey listener, and system tray. |
| `gitcast "your thought here"` | Trigger a capture immediately passing a specific thought or note. |
| `gitcast capture` | Start an interactive terminal screenshot & diff capture session. |
| `gitcast --setup` | Interactive setup to add your personal API key (Groq, Gemini, etc.). |
| `gitcast --version` | Display installed Gitcast version. |

---

## Privacy & Security

- **100% On-Device OCR**: Text from screenshots is extracted locally via Tesseract before any API requests.
- **Automated Secret Scanning**: Regex scanner screens OCR text for API keys (`sk-`, `gsk_`), tokens, passwords, and long hashes, automatically redacting and blocking sensitive captures.
- **Automatic Cleanup**: Screenshots are encrypted with Fernet locally and auto-cleaned after 24 hours. Declined captures are securely deleted immediately.
- **No Background Screen Recording**: Gitcast only captures screen data when explicitly triggered by your hotkey or CLI command.

---

## AI Providers & BYOK Priority

Gitcast routes each post format to the optimal provider for performance and output quality:

| Format | Primary Model | Fallback Model |
|---|---|---|
| **X (Twitter) / Quick Win** | Groq (`llama-3.3-70b`) | Cerebras ➔ OpenRouter |
| **LinkedIn / PR Description** | Groq / DeepSeek | OpenRouter (`qwen3-coder`) |
| **Article & Sprint Thread** | Moonshot / Kimi | Gemini ➔ OpenRouter |
| **Vision Fallback** | Gemini (`gemini-1.5-flash`) | — |

**Key Resolution Priority**:
1. Your personal BYOK key (if set via `gitcast --setup` or saved in `~/.gitcast/.env`).
2. Gitcast built-in shared key (fallback).

---

## Tech Stack

- **Backend**: Python 3.10+, FastAPI, Uvicorn, Pydantic, `httpx`
- **System & Screen**: `mss`, `Pillow`, `pytesseract`, `pynput`, `plyer`
- **AI Engine**: Groq, Google Gemini Vision, OpenRouter, Cerebras, DeepSeek
- **Publishing**: `tweepy` (Twitter/X API v2), Clipboard / Native Web Compose
- **Frontend**: Lightweight responsive dashboard (HTML5, CSS3, JavaScript)

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request or open an Issue on [GitHub](https://github.com/drizzy765/gitcast).

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

Built by [Timilehin Agoro](https://github.com/drizzy765) (@drizzy765).
