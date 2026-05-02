import json
from config.settings import get_project_narrative, is_tone_memory_enabled, PROMPTS_FILE, get_twitter_plan
from storage.tone_memory import get_few_shot_examples
from ai.viral_patterns import get_viral_pattern

# ── PROMPT_MAP ───────────────────────────────────────────────────────────────
PROMPT_MAP = {
    "linkedin": "linkedin_post_prompt",
    "article": "article_prompt"
}


# ── Narrative injection ───────────────────────────────────────────────────────

def _narrative_block() -> str:
    narrative = get_project_narrative()
    if not narrative:
        return ""
    return f"\n\nProject context: The developer is building {narrative}. Where relevant, frame the win or struggle in the context of this larger mission."


def _tone_block() -> str:
    if not is_tone_memory_enabled():
        return ""
    examples = get_few_shot_examples()
    if not examples:
        return ""
    formatted = "\n\n".join(
        f"Example post (highly rated by this user):\n{ex}" for ex in examples
    )
    return f"\n\nHere are examples of posts this developer has written that performed well. Match their voice, tone, and style closely:\n\n{formatted}"


def _plan_block() -> str:
    """
    Returns character limit instructions based on the user's X plan.
    """
    plan = get_twitter_plan()
    if plan == "premium":
        return "\n\nUser Plan: X Premium. You are NOT limited to 280 characters. Feel free to write longer, high-value posts (up to 4000 characters) if the context warrants it."
    else:
        return "\n\nUser Plan: X Free/Basic. You MUST stay under 280 characters for the main post."


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


# ── Prompt Loading ───────────────────────────────────────────────────────────

def load_prompt_definitions() -> dict:
    """Loads prompt templates from the JSON store."""
    if not PROMPTS_FILE.exists():
        return {}
    try:
        with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Prompts] Error loading prompts: {e}")
        return {}


def get_prompt(format_key: str) -> str:
    """Returns the fully assembled system prompt for a given format key."""
    pattern = get_viral_pattern(format_key)
    
    # Check if we have a hardcoded function for this format
    if format_key in PROMPT_MAP:
        func_name = PROMPT_MAP[format_key]
        if func_name == "linkedin_post_prompt":
            template = linkedin_post_prompt()
        elif func_name == "article_prompt":
            template = article_prompt()
        else:
            # Fallback for any other PROMPT_MAP entries
            definitions = load_prompt_definitions()
            template = definitions.get(format_key, {}).get("system_prompt", "")
    else:
        definitions = load_prompt_definitions()
        if format_key not in definitions:
            raise ValueError(f"Unknown prompt format: '{format_key}'")
        template = definitions[format_key]["system_prompt"]
    
    # Assembly with viral pattern injection
    prompt = f"{template}\n\n{pattern}\n\n{BASE_RULES}{_narrative_block()}{_tone_block()}{_plan_block()}"
    return prompt


def get_all_prompts() -> dict[str, str]:
    """Returns all prompts as a dict for parallel generation."""
    definitions = load_prompt_definitions()
    prompts = {key: get_prompt(key) for key in definitions.keys() if key != "sprint_summary"}
    
    # Ensure linkedin and article are included
    if "linkedin" not in prompts:
        prompts["linkedin"] = get_prompt("linkedin")
    if "article" not in prompts:
        prompts["article"] = get_prompt("article")
        
    return prompts


# ── Specialized Prompts ───────────────────────────────────────────────────────

def linkedin_post_prompt() -> str:
    """Professional but human LinkedIn post prompt template."""
    return """You are a developer writing a professional but human post for LinkedIn.

Your goal is to share a technical win or insight in a way that builds your professional brand without sounding like a corporate robot. LinkedIn posts perform best with white space, a strong hook, and a personal narrative.

Format guidance:
- Hook: Line 1 must be a compelling one-sentence hook that stops the scroll.
- The Story: Explain the technical context, the challenge, and how you solved it. Use line breaks for readability.
- The Insight: Share one high-level takeaway that other professionals (not just devs) can appreciate.
- CTA: End with a call to action or a question to your network.
- No hashtag spam (max 3). No generic 'thrilled to announce' filler.

Character target: 800–1300 characters."""


def article_prompt(codebase_summary: str = "") -> str:
    """Generates a full Medium-ready markdown article template."""
    codebase_block = f"\n\nCodebase Summary:\n{codebase_summary}" if codebase_summary else ""
    return f"""You are a developer writing a full Medium-ready technical article in Markdown.

Your goal is to turn the current sprint context and raw thoughts into a structured, high-value technical article that documents your journey and teaches a specific lesson.

Sections to include:
1. Hook: A dramatic opener about the problem or the struggle.
2. Context: What you were building and why it matters.
3. The Journey: The key moments, decisions, and breakthroughs from the logs.
4. Technical Detail: Deep dive into the implementation. Use code snippets from the git diff.
5. Resolution: What is now built and working that wasn't before? What does it unlock?
6. Takeaway: One specific thing other developers can apply to their own work.

Target length: 800–1500 words. Be comprehensive and use Markdown formatting for headers, lists, and code blocks.{codebase_block}"""


def article_refinement_prompt(current_article: str, instruction: str) -> str:
    """Takes existing article draft + user refinement instruction."""
    return f"""You are an editor helping a developer refine their technical article.

Current Article Draft:
---
{current_article}
---

User Instruction: {instruction}

Your job is to update the article based on the user's instruction while maintaining the professional yet human developer voice, the Markdown structure, and the technical depth. Output the COMPLETE updated article.

No preamble. Just the revised Markdown."""


# ── Sprint Mode batch prompt ──────────────────────────────────────────────────

def sprint_summary_prompt(num_captures: int) -> str:
    # Sprint summary is a special case that we'll keep as a function for now
    # or it could also be moved to JSON if needed.
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


if __name__ == "__main__":
    print("=== DYNAMIC PROMPTS TEST ===")
    prompts = get_all_prompts()
    for k, p in prompts.items():
        print(f"\n--- {k.upper()} ---")
        print(p[:200] + "...")
