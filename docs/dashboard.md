# Dashboard

The Gitcast web dashboard runs at http://127.0.0.1:8000

## Layout

Three-column layout:

* **Left sidebar** — navigation, narrative, sprint mode, provider status
* **Main content** — post editor, screenshot strip, AI chat refinement
* **Right panel** — live preview, publish actions

## Tabs

### `[X_POST]`
Generates a tweet optimised for X (Twitter).
Character limit: 280.
Publishes directly via X API v2.
AI chips: Make it viral, Add a hook, Turn into thread, Rage bait, Deep tech version

### `[LINKEDIN]`
Generates a longer professional post for LinkedIn.
Target: 800-1300 characters.
Copy post + download framed screenshot.
AI chips: Corporate tone, Thought leadership, Add statistics, Shorter hook

### `[PR_DESCRIPTION]`
Generates a GitHub PR description from your git diff.
Format: What changed, Why, How, Testing, Notes.
Copies to clipboard for pasting into GitHub.
AI chips: More technical, Add test details, Simplify language, Add risk notes

### `[QUICK_WIN]`
Short punchy update under 200 characters.
Single tweet format.
AI chips: Punchier, Add emoji, More confident, Shorter

## AI Chat Refinement

The command bar at the bottom refines your post in place. Type any instruction and press Ctrl+Enter:

Examples:
- "make it shorter"
- "add a specific number"
- "make the opening more dramatic"
- "turn into a thread"

The post editor updates immediately. Undo with the `← UNDO_LAST_CHANGE` button.

## Screenshot Strip

Shows captured screenshots below the editor.
Accept ✓ or Reject ✗ each screenshot.
Rejected screenshots are deleted from disk immediately.
Accepted screenshots attach to the post on publish.
