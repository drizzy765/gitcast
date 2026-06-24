# Article Generator

Generate Medium-ready markdown articles from your sprint log and codebase.

## Accessing Article Mode

Click `[ARTICLE_MODE]` in the left sidebar.

## How it works

1. Gitcast reads your sprint log entries.
2. Optionally reads your codebase structure.
3. Kimi (128k context) synthesises everything.
4. Returns a structured 800-1500 word article.

## Article structure

- **Hook** — the problem or the struggle
- **Context** — what you were building and why
- **The journey** — key moments from your sprint log
- **Technical detail** — code snippets from your diffs
- **Resolution** — what works now
- **Takeaway** — one thing other developers can apply

## Refining via chat

Use the AI chat to refine:
- "make the intro more dramatic"
- "add more code examples"
- "make it conversational"
- "add a TL;DR at the top"

## Exporting

Click `[EXPORT_AS_MD]` to download as a `.md` file. Paste directly into Medium, dev.to, or Hashnode.

## Including codebase context

Toggle `[INCLUDE_CODEBASE]` before generating.
Gitcast reads key files from your git repo:
- `README.md`
- Main entry points
- Key module files

Caps at 6000 characters to stay within token limits.
