# Contributing to Gitcast

> Thank you for considering contributing to Gitcast.
> Every contribution matters — from bug reports to
> new features to documentation improvements.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Branch Strategy](#branch-strategy)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)
- [Good First Issues](#good-first-issues)

---

## Code of Conduct

Be respectful. Be constructive. Be helpful.
We are all here to build something useful together.
Harassment of any kind will not be tolerated.

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- Tesseract OCR installed locally
  - Windows: github.com/UB-Mannheim/tesseract/wiki
  - Mac: brew install tesseract
  - Linux: sudo apt install tesseract-ocr

### Development Setup

1. Fork the repository on GitHub

2. Clone your fork:
   git clone https://github.com/YOUR_USERNAME/gitcast.git
   cd gitcast

3. Create a virtual environment:
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Mac/Linux

4. Install dependencies:
   pip install -r requirements.txt
   pip install -e .

5. Copy environment file:
   cp .env.example .env

6. Add at least one free API key to .env:
   BYOK_KEY=your_groq_key_here
   Get a free Groq key at console.groq.com

7. Run Gitcast locally:
   gitcast

---

## Branch Strategy

We use a protected main branch with required
pull requests and GitHub Actions checks.

main ← protected, production ready
└── dev ← active development branch
└── feature/your-feature-name
└── fix/bug-description
└── docs/what-you-documented


**Never push directly to main.**
All changes go through a pull request.

Branch naming convention:
- New features:    feature/add-linkedin-scheduler
- Bug fixes:       fix/tesseract-path-detection
- Documentation:   docs/update-contributing-guide
- Refactoring:     refactor/cloud-client-cleanup
- Tests:           test/add-ocr-unit-tests

---

## Making Changes

1. Always branch from dev, not main:
   git checkout dev
   git pull origin dev
   git checkout -b feature/your-feature-name

2. Make your changes in small focused commits:
   git add .
   git commit -m "feat: add LinkedIn post scheduler"

3. Commit message format:
   feat:     new feature
   fix:      bug fix
   docs:     documentation only
   refactor: code change with no feature/fix
   test:     adding or updating tests
   chore:    build process, dependency updates

4. Push your branch:
   git push origin feature/your-feature-name

5. Open a Pull Request against dev (not main)

---

## Pull Request Process

1. Open your PR against the dev branch
2. Fill in the PR template completely
3. GitHub Actions must pass before merge
4. At least one review required
5. Squash and merge is preferred

### PR Title Format
Use the same prefix as commits:
  feat: Add LinkedIn post scheduler
  fix: Resolve Tesseract path detection on Windows
  docs: Update installation instructions

### What Makes a Good PR
- One focused change per PR
- Clear description of what changed and why
- Screenshots or terminal output for UI changes
- Tests added or updated if relevant
- No merge conflicts with dev branch

---

## Reporting Bugs

Open an issue at:
github.com/drizzy765/gitcast/issues

Use this format:

**Gitcast version:**
pip show gitcast | grep Version

**OS:**
Windows 10 / macOS 13 / Ubuntu 22.04

**Steps to reproduce:**
1. Run gitcast from directory X
2. Press Ctrl+Shift+P
3. See error

**Expected behavior:**
What should have happened

**Actual behavior:**
What actually happened

**Terminal output:**
Paste the full terminal output here

**Screenshots:**
If applicable

---

## Suggesting Features

Open an issue with the label `enhancement`.

Describe:
- The problem you are trying to solve
- Your proposed solution
- Alternatives you considered
- Who else would benefit from this

We prioritize features that:
- Reduce friction in the capture → publish flow
- Improve post quality and relevance
- Strengthen privacy guarantees
- Work across Windows, Mac, and Linux

---

## Good First Issues

Look for issues labeled `good first issue` on GitHub.
These are intentionally scoped to be approachable
for first-time contributors.

Current areas where contributions are welcome:
- Linux and macOS testing and bug fixes
- Additional AI provider integrations
- Improved OCR confidence for dark themes
- Documentation and example improvements
- Unit tests for core modules
- Translation of the dashboard UI

---

## Project Structure

gitcast/
├── cli/gitcast.py         entry point
├── core/
│   ├── capture.py         screenshot + git diff
│   ├── ocr.py             local text extraction
│   ├── trigger.py         hotkey → capture flow
│   ├── tray.py            system tray
│   └── project_reader.py  README + stack detection
├── ai/
│   ├── prompts.py         system prompts
│   └── generator.py       cloud AI routing
├── api/
│   ├── server.py          local FastAPI server
│   ├── routes.py          API endpoints
│   └── payload.py         payload assembly
├── publisher/
│   ├── twitter.py         X API v2
│   └── clipboard.py       clipboard fallback
├── storage/
│   ├── logger.py          local post log
│   └── sprint.py          sprint mode captures
├── config/
│   └── settings.py        all configuration
└── web/
    └── index.html         dashboard

---

## Questions?

Open a discussion on GitHub or reach out on X:
twitter.com/timilovesml1234

Built with care in Nigeria.
Every ship deserves a log.
