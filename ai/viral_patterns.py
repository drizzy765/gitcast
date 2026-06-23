# [ViralPatterns] module for structural guidance in prompt building

VIRAL_STRUCTURES = {
    "hot_take": """Optional Structural Guidance (adapt to the developer's prompt if one is provided):
- Lead with an engaging, opinionated opener related to the topic.
- Use a supporting observation or detail from the context.
- Invite discussion or feedback in the closing line.""",

    "confession": """Optional Structural Guidance (only apply if the developer is sharing a struggle/bug):
- Open with the symptom or frustration to hook the reader.
- Briefly explain what didn't work and the key breakthrough/fix.
- Share a lesson learned or invite others to share similar stories.""",

    "technical_flex": """Optional Structural Guidance (only apply if the developer is sharing a win/performance improvement):
- Lead with a concrete metric, improvement, or milestone.
- Provide a clear, one-line technical explanation of how it was achieved.
- Share a sharp, confident insight about the engineering approach.""",

    "thread_hook": """Optional Structural Guidance (for threads):
- Start with a compelling, open-ended hook/question as the first tweet.
- Break down the implementation or narrative sequentially across tweets.
- Number the tweets (1/, 2/, etc.) for flow.""",

    "opinion_mode": """Optional Structural Guidance (only apply if the developer's prompt is about sharing a general opinion/stance):
- State a clear stance on a developer ecosystem topic or practice.
- Back it up with specific developer experience rather than general theory.
- End with an engaging question to the community.""",

    "build_confession": """Optional Structural Guidance (only apply if the developer's prompt is about a struggle or complex feature):
- Set up the challenge and why it was difficult.
- Highlight the breakthrough or key design choice.
- Show the current working outcome.""",

    "linkedin_narrative": """Optional Structural Guidance (for LinkedIn style):
- Hook: A scroll-stopping opening line highlighting the project, milestone, or challenge.
- Spacing: Use double line breaks between short paragraphs (1-2 sentences max) to ensure clean readability on mobile devices.
- Narrative: Tell a relatable story: the challenge/goal, the process, and the breakthrough/launch.
- Professional Takeaway: Share a high-level lesson or insight that other tech professionals or builders can apply.
- CTA: End with an engaging question to invite comments (e.g., asking for feedback or experiences).""",

    "velocity_update": """Optional Structural Guidance (for quick status updates):
- Lead with the direct outcome (e.g., 'Just shipped...', 'Fixed the...').
- Provide a single sentence of technical context.
- End with forward momentum (what this unlocks next).""",

    "pr_template": """Optional Structural Guidance (for Pull Requests):
- Markdown layout with clear headings (What changed, Why, How, Testing, Notes).
- Technical details referencing actual files, functions, or changes.
- Neutral, documentation-focused tone."""
}

def get_viral_pattern(format_key: str) -> str:
    """Returns a pattern prompt snippet based on the format key."""
    # Mapping certain format keys to specific patterns
    mapping = {
        "deep_tech": "technical_flex",
        "struggle": "confession",
        "quick_win": "velocity_update",
        "linkedin": "linkedin_narrative",
        "pr_generator": "pr_template",
        "thought": "hot_take"
    }
    
    pattern_key = mapping.get(format_key, "opinion_mode")
    return VIRAL_STRUCTURES.get(pattern_key, "")

def get_all_patterns() -> dict:
    """Returns the full dictionary of viral structures."""
    return VIRAL_STRUCTURES

if __name__ == "__main__":
    print("=== VIRAL PATTERNS TEST ===")
    for key in ["deep_tech", "struggle", "unknown"]:
        print(f"\n--- Pattern for {key} ---")
        print(get_viral_pattern(key))
