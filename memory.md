# Context Engine Handoff - 2026-06-22

We have successfully aligned the generation backend with the UI tabs and ensured the AI respects custom developer prompt instructions (such as project introductions) across all post generation modes.

## User Intent
* Ensure the AI understands the unique context for LinkedIn, X (Twitter), PR descriptions, and Quick Wins.
* Ensure user prompts (e.g., "introductory post to introduce my project") take priority in all modes rather than being overridden by narrow templates.

## Files Changed
1. **[api/payload.py](file:///mnt/c/Users/USER/Documents/context-engine/api/payload.py#L21):**
   * Changed the default `format_keys` list to match active UI tabs: `["deep_tech", "linkedin", "pr_generator", "quick_win"]` (instead of generating `struggle` which was hidden from the UI, and missing `linkedin`).
2. **[ai/viral_patterns.py](file:///mnt/c/Users/USER/Documents/context-engine/ai/viral_patterns.py):**
   * Refined structural guidance patterns (e.g. `linkedin_narrative`, `velocity_update`, `pr_template`) to be suggestive/optional. This prevents them from conflicting with or overriding custom developer topics.
3. **[ai/prompts.py](file:///mnt/c/Users/USER/Documents/context-engine/ai/prompts.py):**
   * Updated `get_prompt` to check prompt definitions from `prompts.json` first, allowing full UI customization.
   * Relaxed `BASE_RULES` to allow developer raw thoughts/prompts to override default constraints (e.g. allowing expression of excitement if requested).
4. **[storage/data/prompts.json](file:///mnt/c/Users/USER/Documents/context-engine/storage/data/prompts.json):**
   * Pre-registered the `linkedin` prompt configuration to make it visible and customizable in the Prompt Management settings view.
   * Updated all platform prompt templates to include: `IMPORTANT: Prioritize the developer's raw thought/prompt if one is provided.`
5. **[api/routes.py](file:///mnt/c/Users/USER/Documents/context-engine/api/routes.py#L887):**
   * Modified the `/chat` refinement endpoint to dynamically retrieve the platform-specific rules using `get_prompt` and inject them into the refinement prompt, keeping iterative edits context-aware.

## Verification Completed
* Ran the `build_payload` unit test in [tests/test_ocr_fix.py](file:///mnt/c/Users/USER/Documents/context-engine/tests/test_ocr_fix.py#L13) successfully, verifying no runtime syntax or structure breakages.

## Resume Next Steps
1. Start the app local server.
2. Trigger a capture and verify that the `LinkedIn` post generates alongside X (`deep_tech`), PR description (`pr_generator`), and Quick Win (`quick_win`).
3. Test writing a custom developer prompt (e.g. "write an introductory post to introduce my project") in the UI capture input to ensure the AI creates a clean intro post tailored for all 4 platforms.
4. Tweak specific system prompts or lengths in the Prompt Management UI if any final refinement is needed.

---

# Project Rebranding: Shiplog -> Gitcast

We have successfully renamed the project from **Shiplog** to **Gitcast** across the entire codebase and static pages.

## Changes Made
1. **Codebase Renaming:**
   * Replaced all references to `Shiplog` / `SHIPLOG` / `shiplog` with `Gitcast` / `GITCAST` / `gitcast` across files including [main.py](file:///mnt/c/Users/USER/Documents/context-engine/main.py), [api/server.py](file:///mnt/c/Users/USER/Documents/context-engine/api/server.py), [cli.py](file:///mnt/c/Users/USER/Documents/context-engine/cli.py), [core/capture.py](file:///mnt/c/Users/USER/Documents/context-engine/core/capture.py), [core/screenshot_session.py](file:///mnt/c/Users/USER/Documents/context-engine/core/screenshot_session.py), [core/tray.py](file:///mnt/c/Users/USER/Documents/context-engine/core/tray.py), [web/index.html](file:///mnt/c/Users/USER/Documents/context-engine/web/index.html), and [web/landing.html](file:///mnt/c/Users/USER/Documents/context-engine/web/landing.html).
2. **ASCII Art Brand Marks:**
   * Updated both [web/index.html](file:///mnt/c/Users/USER/Documents/context-engine/web/index.html#L1923-L1928) and [web/landing.html](file:///mnt/c/Users/USER/Documents/context-engine/web/landing.html#L486-L491) to render the new `GITCAST` ASCII block art logo:
     ```
      ██████╗ ██╗████████╗ ██████╗   █████╗  ███████╗████████╗
     ██╔════╝ ██║╚══██╔══╝██╔════╝  ██╔══██╗ ██╔════╝╚══██╔══╝
     ██║  ███╗██║   ██║   ██║       ███████║ ███████╗   ██║   
     ██║   ██║██║   ██║   ██║       ██╔══██║ ╚════██║   ██║   
     ╚██████╔╝██║   ██║   ╚██████╗  ██║  ██║ ███████║   ██║   
      ╚═════╝ ╚═╝   ╚═╝    ╚═════╝  ╚═╝  ╚═╝ ╚══════╝   ╚═╝   
     ```

## Verification
* Confirmed all `shiplog` instances are removed from active codebase directories (verified via `grep`).
* Verified the landing page `/` and web app route `/app` on the local server at `http://127.0.0.1:8000` serve only `Gitcast` references.
* The local server is restarted and running under background task `task-378`.
