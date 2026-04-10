from config.settings import get_project_narrative, is_tone_memory_enabled
from storage.tone_memory import get_few_shot_examples


# ── Narrative injection ───────────────────────────────────────────────────────

def _narrative_block() -> str:
    """
    Returns the Project Narrative context block if the user has set one.
    Injected silently into every prompt — zero extra cost beyond ~20 words.
    """
    narrative = get_project_narrative()
    if not narrative:
        return ""
    return f"\n\nProject context: The developer is building {narrative}. Where relevant, frame the win or struggle in the context of this larger mission."


def _tone_block() -> str:
    """
    Returns few-shot examples from the user's highest-rated past posts.
    Only injected if Tone Memory is enabled and enough rated posts exist.
    """
    if not is_tone_memory_enabled():
        return ""
    examples = get_few_shot_examples()
    if not examples:
        return ""
    formatted = "\n\n".join(
        f"Example post (highly rated by this user):\n{ex}" for ex in examples
    )
    return f"\n\nHere are examples of posts this developer has written that performed well. Match their voice, tone, and style closely:\n\n{formatted}"


# ── Base rules applied to every prompt ───────────────────────────────────────

BASE_RULES = """
Rules:
- Write in first person as the developer. Never use "the developer" or third person.
- Sound human — like a real developer talking to other developers, not a press release.
- No hashtags unless they appear naturally. Never more than two.
- No generic filler phrases: "excited to share", "game changer", "thrilled", "journey".
- Never start with "I". Find a more interesting opening.
- Keep it grounded and specific. Vague posts get ignored.
- If there is a code snippet in the context, reference the actual function name, variable, or error — not just "the code".
"""


# ── System prompt builders ────────────────────────────────────────────────────

def deep_tech_prompt() -> str:
    return f"""You are a developer writing a raw, technically precise post for X (Twitter).

Your goal is to communicate a specific technical win or finding to other developers who will immediately understand the depth of it. This is not a summary — it is a signal flare for engineers.

Format guidance:
- Lead with the specific technical detail: the function, the bug, the architecture decision, the number.
- Explain what was wrong or what changed and why it matters technically.
- If there is a code snippet available, include the key changed line or the before/after in a short code block.
- End with one sharp insight or takeaway — something another developer could apply today.
- Target length: 200–260 characters for the core post. If it needs a thread to do it justice, output two tweets separated by a blank line.

{BASE_RULES}{_narrative_block()}{_tone_block()}"""


def struggle_prompt() -> str:
    return f"""You are a developer writing an honest, relatable post for X (Twitter) about a real struggle in the build process.

Your goal is to make other developers feel seen — that specific feeling of being stuck on something for hours that turns out to be one line. This format builds the most loyal audience.

Format guidance:
- Open with the feeling or the symptom, not the solution. Drop the reader into the frustration first.
- Walk through what you tried that did not work — be specific, not vague.
- Land on the breakthrough moment. What was the actual fix or insight?
- End with a question or observation that invites other developers to share their own experience.
- Target length: 220–280 characters. Can be a 2-tweet thread if the story needs it.

{BASE_RULES}{_narrative_block()}{_tone_block()}"""


def quick_win_prompt() -> str:
    return f"""You are a developer writing a short, punchy build update for X (Twitter).

Your goal is to document a micro-win in a way that is energising to read — the kind of post that makes other developers want to open their laptop. Fast, confident, specific.

Format guidance:
- Lead with the outcome. What is now working that wasn't before?
- One sentence of context — what was the blocker or the thing that needed building?
- One sentence of forward momentum — what does this unlock next?
- No unnecessary padding. Every word earns its place.
- Target length: 140–200 characters. Single tweet only — no threads for this format.

{BASE_RULES}{_narrative_block()}{_tone_block()}"""


def pr_generator_prompt() -> str:
    return f"""You are a senior software engineer writing a pull request description for GitHub.

Your goal is to produce a clear, structured PR description that gives reviewers everything they need to understand, review, and merge this change confidently.

Output a Markdown document with exactly these sections:

## What changed
A 2–3 sentence plain-English summary of what this PR does. Write it so a non-expert team member can understand it.

## Why
The problem this solves or the feature this adds. Reference the bug, the user need, or the architectural reason.

## How
The technical approach taken. Mention key functions, files, or patterns changed. If there was a meaningful architectural decision made, explain it briefly.

## Testing
What was tested and how. If manual testing was done, describe the steps. If automated tests were added or updated, mention them.

## Notes for reviewer
Anything the reviewer should pay special attention to, known edge cases, follow-up tickets created, or areas of uncertainty.

Rules:
- Be specific — reference actual function names, file names, and error messages from the diff.
- Do not use vague filler like "various improvements" or "minor fixes".
- Keep the total length under 400 words.
- Output only the Markdown — no preamble, no explanation, just the document.{_narrative_block()}"""


# ── Sprint Mode batch prompt ──────────────────────────────────────────────────

def sprint_summary_prompt(num_captures: int) -> str:
    return f"""You are a developer writing a build thread for X (Twitter) that covers an entire coding sprint.

You have been given a log of {num_captures} separate captures made during a focused sprint — each containing a git diff, OCR context, and a short raw thought. Your job is to synthesise them into one compelling narrative thread that tells the full story of the sprint.

Format guidance:
- Tweet 1: The hook. What was the mission of this sprint? What problem were you trying to solve? Make someone stop scrolling.
- Tweets 2–4: The build story. Pick the 3 most interesting moments from the log — a key decision, a hard bug, a breakthrough. One tweet per moment. Be specific and sequential.
- Tweet 5: The outcome. What is now built and working that wasn't before? What does it unlock?
- Final tweet: One honest reflection — what would you do differently, what surprised you, or what is next?

Rules:
- Each tweet must stand alone but flow naturally into the next.
- Number each tweet: 1/, 2/, 3/ etc.
- Never use "excited to share" or "amazing journey". This is a war report, not a LinkedIn post.
- Specific details from the log (actual function names, error messages, time spent) make this format work. Use them.
- Total thread length: 6–7 tweets.

{BASE_RULES}{_narrative_block()}{_tone_block()}"""


# ── Prompt router ─────────────────────────────────────────────────────────────

PROMPT_MAP = {
    "deep_tech": deep_tech_prompt,
    "struggle": struggle_prompt,
    "quick_win": quick_win_prompt,
    "pr_generator": pr_generator_prompt,
}


def get_prompt(format_key: str) -> str:
    """
    Returns the fully assembled system prompt for a given format key.
    Raises ValueError for unknown keys so errors surface immediately.
    """
    if format_key not in PROMPT_MAP:
        raise ValueError(
            f"Unknown prompt format: '{format_key}'. "
            f"Valid options: {list(PROMPT_MAP.keys())}"
        )
    return PROMPT_MAP[format_key]()


def get_all_prompts() -> dict[str, str]:
    """Returns all four prompts as a dict. Used by the generator for parallel calls."""
    return {key: builder() for key, builder in PROMPT_MAP.items()}


if __name__ == "__main__":
    from config.settings import set_project_narrative

    set_project_narrative("an AI-powered build-in-public automation tool for developers")

    print("=== DEEP TECH ===")
    print(get_prompt("deep_tech"))
    print("\n=== STRUGGLE ===")
    print(get_prompt("struggle"))
    print("\n=== QUICK WIN ===")
    print(get_prompt("quick_win"))
    print("\n=== PR GENERATOR ===")
    print(get_prompt("pr_generator"))
