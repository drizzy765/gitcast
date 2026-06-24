# AI Providers

Gitcast uses task-specific routing across multiple free-tier AI providers.

## Why multiple providers?

No single free tier has enough capacity for all tasks. By routing different tasks to different models:
- Rate limits are distributed across providers
- Each task uses the model best suited for it
- Automatic fallback means generation rarely fails

## Provider details

### Groq
Speed-optimised inference. Fastest response times.
* Model: `llama-3.3-70b-versatile`
* Best for: Short posts where latency matters

### DeepSeek
Code-aware model. Understands git diffs semantically.
* Model: `deepseek-chat` (DeepSeek V3)
* Best for: Technical posts, PR descriptions

### Gemini
Multimodal — can read screenshots directly.
* Model: `gemini-1.5-flash`
* Best for: When OCR confidence is below 60%

### Kimi (Moonshot)
128k context window. Handles large codebases.
* Model: `moonshot-v1-128k`
* Best for: Articles, sprint summaries

### OpenRouter
Gateway to 50+ models including free tiers.
* Model: `meta-llama/llama-3.3-70b-instruct:free`
* Best for: Automatic overflow fallback

### Cerebras
Fastest inference hardware available.
* Model: `llama3.3-70b`
* Best for: Groq backup during rate limits

## Fallback chain

If a provider is rate limited or unavailable, Gitcast automatically tries the next in the chain. The live log panel shows which provider handled each request in real time.
