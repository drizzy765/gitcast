# Sprint Mode

Capture silently during deep work sessions. Generate one comprehensive thread when you surface.

## How it works

### Activating Sprint Mode
Toggle Sprint Mode from the left sidebar or tray menu. A green `[ON]` indicator confirms it's active.

### During Sprint Mode
Every Ctrl+Shift+P press:
- Captures screenshot and git diff silently
- No popup appears
- No AI call made
- Capture saved to `storage/data/sprint_log.txt`
- Terminal shows: `[Gitcast] Sprint capture logged silently`

Zero interruption to your flow.

### Ending Sprint Mode
Toggle Sprint Mode off.
Gitcast reads the entire sprint log (20-50 captures) and makes one API call to generate:
- A 6-7 tweet thread covering the full sprint arc
- Hook tweet, 3-4 build moments, outcome, reflection

### Why Sprint Mode produces better content
The AI sees the full arc of your work — not isolated moments. It can construct a narrative: what you were trying to do, what went wrong, what you tried, what finally worked. This is the highest-engagement content format on developer Twitter.

## Sprint log location

`storage/data/sprint_log.txt`

Each entry contains: timestamp, raw thought, git diff, OCR text.

## Clearing the log

After generating a sprint thread the log clears automatically. You can also clear manually from Settings.
