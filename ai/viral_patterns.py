# [ViralPatterns] module for structural guidance in prompt building

VIRAL_STRUCTURES = {
    "hot_take": """Structure:
- Strong, controversial opinion opener related to the technical task.
- One supporting data point or observation from the current context.
- Invite disagreement or debate in the closing line.""",

    "confession": """Structure:
- Admit something went wrong or a mistake you made.
- Specific technical detail of the failure.
- What you did to fix it.
- One key lesson learned.""",

    "technical_flex": """Structure:
- Lead with a concrete metric, benchmark, or before/after number.
- One line technical explanation of how you achieved it.
- A sharp, confident insight about the implementation.""",

    "thread_hook": """Structure:
- A compelling, open-ended question as the first tweet.
- Promise a specific technical answer that unfolds across the thread.
- Use '1/' to indicate the start.""",

    "opinion_mode": """Structure:
- Take a firm stance on a developer ecosystem topic (languages, frameworks, tools).
- Back it with specific experience from the current capture, not theory.
- End with a question to the community.""",

    "build_confession": """Structure:
- Start with: "I almost gave up on [Feature] because [Obstacle]."
- Describe the 'lightbulb moment' from the logs.
- Show the current working state."""
}

def get_viral_pattern(format_key: str) -> str:
    """Returns a pattern prompt snippet based on the format key."""
    # Mapping certain format keys to specific patterns
    mapping = {
        "deep_tech": "technical_flex",
        "struggle": "confession",
        "quick_win": "build_confession",
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
