# Gitcast

> git diff → published post. under 60 seconds.

Privacy-first developer tool that captures your
coding session via hotkey, generates AI-powered
social media posts, and publishes them — without
breaking your flow.

Works out of the box with zero setup. Bring your
own API keys anytime for unlimited usage.

    pip install gitcast
    gitcast

Press Ctrl+Alt+S to capture. Open source. MIT license.

## Quick Start

### Install

    pip install gitcast

### Run

    gitcast

That's it. Gitcast works immediately using a shared
demo API key — no setup required to try it.

Dashboard opens automatically at http://localhost:8000

Press **Ctrl+Alt+S** (or **Ctrl+Shift+P**) from
anywhere — VS Code, terminal, browser — to capture
your screen and git diff, then generate a post.

### Add your own API key (optional)

The shared key has rate limits. For unlimited usage,
add your own free key:

    gitcast --setup

This opens your .env file. Add any of these
(all free):

| Provider | Get Key | Free Tier |
|----------|---------|-----------|
| Groq | console.groq.com | 12k tokens/min |
| DeepSeek | platform.deepseek.com | $5 credit |
| Gemini | aistudio.google.com | 1M tokens/day |

Your key always takes priority over the shared key.

### CLI usage

    gitcast                    Start dashboard + hotkey listener
    gitcast "your thought"     Quick capture with inline thought
    gitcast capture            Interactive multi-shot screenshot session
    gitcast --setup            Configure your own API keys
    gitcast --version          Show version

## Stack
- Python 3.11+
- FastAPI, pynput, mss, Tesseract, Groq API, Tweepy
