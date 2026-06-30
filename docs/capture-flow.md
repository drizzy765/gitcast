# Capture Flow

How Gitcast captures context without breaking your flow.

## The 7-step flow

## Trigger

Press **Ctrl+Alt+S** or **Ctrl+Shift+P** from
anywhere — VS Code, terminal, browser. Both
hotkeys trigger the same capture flow. The pynput listener runs silently in the system tray.

### 2. Parallel capture
Two things happen simultaneously:
- mss takes a screenshot of your active window
- subprocess runs `git diff HEAD` in your working directory

Both happen before any popup appears.

### 3. Local OCR
Tesseract extracts visible text from the screenshot. If confidence is below 60%, the screenshot routes to Gemini vision instead. Nothing has left your machine yet.

### 4. Input prompt
A minimal popup appears with one question:
"What was the struggle or win?"
Type a raw unformatted thought. Enter to submit. Esc to cancel — everything is discarded silently.

### 5. AI generation
FastAPI assembles the payload and fires 4 completions in parallel — one per post format. Total latency: 4-8s.

### 6. Review
The dashboard shows all 4 variations with your screenshot preview. Edit inline, use AI chat to refine.

### 7. Publish
One click to X via API. LinkedIn copy + download. PR description copies to clipboard.

## Privacy guarantees

- OCR text never logged or stored permanently
- Git diff never stored after generation
- Screenshots deleted after 24 hours by default
- Sensitive content (API keys, passwords) auto-blocked
- Declined captures deleted immediately from disk

## Edge cases

| Situation | Behaviour |
|-----------|-----------|
| No git repo | Screenshot + OCR only, continues normally |
| Low OCR confidence | Routes to Gemini vision |
| User presses Esc | Everything discarded, no API call |
| No internet | Payload saved locally for retry |
| Sensitive content detected | Screenshot deleted, capture cancelled |
