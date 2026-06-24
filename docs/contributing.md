# Contributing

Gitcast is open source and welcomes contributions.

## Ways to contribute

- **Bug reports** — open an issue with steps to reproduce
- **Feature requests** — open an issue with use case
- **Code** — open a PR with your changes
- **Docs** — fix typos, add examples, improve clarity
- **Translations** — help localise the dashboard

## Development setup

```bash
git clone https://github.com/drizzy765/gitcast.git
cd gitcast
python -m venv venv
source venv/bin/activate  # Or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# add at least one API key to .env
python main.py
```

## Project structure

```text
gitcast/
├── main.py              # Entry point
├── core/                # Capture, OCR, hotkey, tray icon
├── ai/                  # Prompts, generator, viral patterns
├── api/                 # FastAPI server, routes, validators
├── publisher/           # X API, clipboard fallback
├── storage/             # Logger, metrics, insights, sync
├── config/              # Settings, key management
├── web/                 # Dashboard (index.html) + landing page
├── docs/                # Documentation
└── tests/               # Unit tests
```

## PR guidelines

- One feature or fix per PR
- Include a test if adding new functionality
- Update docs if changing behaviour
- Run `py_compile` on changed files before submitting

## Code style

- Python 3.10
- Print prefix: `[ModuleName]`
- Return pattern: `{"success": bool, "error": str}`
- No type hints narrower than `list`, `dict`
