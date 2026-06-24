# API Keys Guide

Gitcast uses a BYOK (Bring Your Own Key) model. Your keys stay on your machine. We never see them.

## Why BYOK?

- Your data stays private
- You control your costs
- No subscription required
- All listed providers have generous free tiers

## Getting each key

### Groq (Start here — fastest)

1. Go to console.groq.com
2. Sign up with GitHub or Google
3. Click **API Keys** → **Create API Key**
4. Copy the key starting with `gsk_`
5. Add to `.env`: `GROQ_API_KEY=gsk_...`

* Free tier: 12,000 tokens per minute
* Used for: Quick Win, LinkedIn, Struggle posts

### DeepSeek (Best for technical posts)

1. Go to platform.deepseek.com
2. Sign up → **API Keys** → **Create**
3. Copy the key starting with `sk-`
4. Add to `.env`: `DEEPSEEK_API_KEY=sk-...`

* Free tier: $5 credit on signup
* Used for: Deep Tech posts, PR descriptions

### Gemini (Required for vision fallback)

1. Go to aistudio.google.com
2. Sign in with Google
3. Click **Get API Key** → **Create API key**
4. Add to `.env`: `GEMINI_API_KEY=...`

* Free tier: 1 million tokens per day
* Used for: Screenshots with low OCR confidence

### Kimi / Moonshot (Best for articles)

1. Go to platform.moonshot.cn
2. Sign up (use Chrome auto-translate if needed)
3. **API Keys** → **Create**
4. Add to `.env`: `MOONSHOT_API_KEY=...`

* Free tier: 15 RPM
* Used for: Article generation, Sprint Mode summaries

### OpenRouter (Best backup)

1. Go to openrouter.ai
2. Sign up → **Keys** → **Create Key**
3. Add to `.env`: `OPENROUTER_API_KEY=sk-or-...`

* Free tier: Access to 50+ free models
* Used for: Automatic fallback when other providers hit rate limits

## Provider routing

Gitcast automatically routes each task to the best available provider:

| Task | Primary | Fallback |
|------|---------|----------|
| Quick Win | Groq | Cerebras → OpenRouter |
| Struggle | Groq | Cerebras → OpenRouter |
| LinkedIn | Groq | DeepSeek → OpenRouter |
| Deep Tech | DeepSeek | Groq → OpenRouter |
| PR Description | DeepSeek | Groq → OpenRouter |
| Article | Kimi | Gemini → OpenRouter |
| Sprint Summary | Kimi | Gemini → OpenRouter |
| Vision fallback | Gemini | — |
