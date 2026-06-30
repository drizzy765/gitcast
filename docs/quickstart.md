# Quick Start

Get Gitcast running in under 2 minutes.

## Step 1 — Install

    pip install gitcast

## Step 2 — Install Tesseract OCR

Required for local screenshot text extraction.

**Windows:** github.com/UB-Mannheim/tesseract/wiki
**Mac:** brew install tesseract
**Linux:** sudo apt install tesseract-ocr

## Step 3 — Run

    gitcast

Gitcast starts immediately using a shared demo
API key. No configuration needed for your first
posts.

You'll see:

    > [OK] using Gitcast shared API key
    > // want your own key? run: gitcast --setup
    > [OK] server running at http://localhost:8000
    > [OK] browser opened
    > Press Ctrl+Alt+S (or Ctrl+Shift+P) to capture

## Step 4 — Capture your first win

From any window — VS Code, terminal, browser —
press **Ctrl+Alt+S**.

Gitcast captures your screen and git diff locally,
asks what you were working on, and generates
4 post variations.

## Step 5 (optional) — Add your own API key

The shared key has limited capacity. To remove
limits, get your own free key:

    gitcast --setup

Add at least one key (Groq recommended first —
takes 2 minutes at console.groq.com). Your key
automatically overrides the shared one.
