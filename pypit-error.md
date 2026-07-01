# Gitcast Execution Error Log: 401 Unauthorized & Post Generation Failure

This document records the details, root cause analysis, and proposed resolutions for the execution issues encountered when running `gitcast` in a new directory (`snakegame`) using a different virtual environment and IDE.

---

## 1. Error Details

### Environment
- **Target Directory**: `C:\Users\USER\Documents\snakegame`
- **Gitcast Version**: `1.0.10` (installed via pip)
- **Execution Command**: `gitcast`

### Terminal Output
```text
Installing collected packages: gitcast
Successfully installed gitcast-1.0.10
WARNING: You are using pip version 21.2.3; however, version 26.1.2 is available.
You should consider upgrading via the 'C:\Users\USER\Documents\context-engine\venv\Scripts\python.exe -m pip install --upgrade pip' command.
(venv) PS C:\Users\USER\Documents\snakegame> gitcast
[Monitoring] Sentry not configured - skipping

[Auth] Session Token: 07606449-be52-4296-a1f4-ab67c4cd5a5d
[Server] Starting Gitcast API on http://127.0.0.1:8000

[Auth] Session Token: 07606449-be52-4296-a1f4-ab67c4cd5a5d
[Server] Starting Gitcast API on http://127.0.0.1:8000
[OK] server running at http://localhost:8000
[OK] browser opened
```

### Browser Console Logs
```text
contentscript.js:14083 MaxListenersExceededWarning: Possible EventEmitter memory leak detected. 11 close listeners added. Use emitter.setMaxListeners() to increase limit
n @ contentscript.js:14083
contentscript.js:14083 MaxListenersExceededWarning: Possible EventEmitter memory leak detected. 11 end listeners added. Use emitter.setMaxListeners() to increase limit
n @ contentscript.js:14083
2contentscript.js:14083 ObjectMultiplex - orphaned data for stream "app-init-liveness"
warn @ contentscript.js:14083
2contentscript.js:14083 ObjectMultiplex - orphaned data for stream "background-liveness"
warn @ contentscript.js:14083
2contentscript.js:14083 ObjectMultiplex - malformed chunk without name "[object Object]"
warn @ contentscript.js:14083
api/keys/status:1  Failed to load resource: the server responded with a status of 401 (Unauthorized)
```

---

## 2. Root Cause Analysis

### Issue A: 401 Unauthorized API Response (`/api/keys/status`)
1. **Token Lifecycle**:
   - Every time `gitcast` starts, it generates a fresh random `SESSION_TOKEN` in [api/auth.py](file:///mnt/c/Users/USER/Documents/context-engine/api/auth.py#L11).
   - In this run, the session token was initialized as `07606449-be52-4296-a1f4-ab67c4cd5a5d`.
2. **Frontend Authentication Check**:
   - Upon page load, the frontend script `authGate()` in [web/index.html](file:///mnt/c/Users/USER/Documents/context-engine/web/index.html#L2354) checks if it is running on `localhost`.
   - If on `localhost`, it attempts to fetch the current active session token from `/api/token`.
   - If `/api/token` returns `200 OK`, it uses the fetched token.
   - If `/api/token` fails (non-200), the frontend falls back to retrieving the last saved token from `localStorage.getItem('sl_token')` which holds the expired token from the previous run (in `context-engine`).
   - It then validates this token by querying `/api/keys/status`. Because the old token does not match the new session token, the FastAPI backend rejects the request with a `401 Unauthorized` status.
3. **Why `/api/token` Failed**:
   - In [api/server.py](file:///mnt/c/Users/USER/Documents/context-engine/api/server.py#L129), `/api/token` restricts access using:
     ```python
     client_host = request.client.host if request.client else None
     if client_host not in ["127.0.0.1", "localhost", "::1"]:
         raise HTTPException(status_code=403, detail="Forbidden: Access allowed only from localhost")
     ```
   - On certain platforms or dual-stack IPv4/IPv6 network setups, the browser's request host can be mapped as an IPv4-mapped IPv6 address (e.g. `::ffff:127.0.0.1`).
   - Because `::ffff:127.0.0.1` is not in the whitelist, the backend returns a `403 Forbidden` response. The frontend fails to retrieve the new session token and falls back to the old one in `localStorage`, leading to the `401 Unauthorized` console log.

### Issue B: Post Generation Fails to Trigger
1. **Working Directory Resolution**:
   - In [core/capture.py](file:///mnt/c/Users/USER/Documents/context-engine/core/capture.py#L185), `detect_working_directory()` determines the active directory to scan for Git changes:
     ```python
     candidates = [
         Path(__file__).resolve().parent.parent,  # project root
         Path.cwd(),
         Path(os.environ.get("USERPROFILE", "")) / "Documents" / "context-engine",
         Path.home(),
     ]
     ```
   - When running from `snakegame`, `Path.cwd()` is `C:\Users\USER\Documents\snakegame`.
   - If `snakegame` is not initialized as a Git repository, `git rev-parse --show-toplevel` fails for it.
   - The loop then checks the next candidate: `C:\Users\USER\Documents\context-engine`. Since this is a valid Git repository, it successfully resolves as the active working directory.
   - Consequently, `gitcast` captures the git history and diffs of the `context-engine` project instead of `snakegame`, resulting in no posts being generated because there are no new changes in the context-engine repo.

---

## 3. Proposed Fixes

### Fix 1: Robust Localhost Detection for `/api/token`
Update [api/server.py](file:///mnt/c/Users/USER/Documents/context-engine/api/server.py#L129) to handle IPv4-mapped IPv6 addresses (like `::ffff:127.0.0.1`):
```python
@app.get("/api/token")
def get_session_token(request: Request):
    client_host = request.client.host if request.client else None
    if client_host:
        # Normalize IPv4-mapped IPv6 address
        if client_host.startswith("::ffff:"):
            client_host = client_host.replace("::ffff:", "")
            
    if client_host not in ["127.0.0.1", "localhost", "::1"]:
        raise HTTPException(status_code=403, detail="Forbidden: Access allowed only from localhost")
    return {"token": get_token()}
```

### Fix 2: Remove Hardcoded Dirs from `detect_working_directory()`
Update [core/capture.py](file:///mnt/c/Users/USER/Documents/context-engine/core/capture.py#L185) to avoid falling back to other project paths like `context-engine` when running from an unrelated directory:
```python
def detect_working_directory() -> str:
    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parent.parent,
        Path.home(),
    ]
    ...
```
This ensures `gitcast` remains scoped to the current directory where the user initiated the command.

---

## 4. Execution Issues in New Directory (Snakegame) - 2026-06-29

### Terminal Log Output
```text
(venv) PS C:\Users\USER\Documents\snakegame> gitcast
[Monitoring] Sentry not configured - skipping

[Auth] Session Token: cb7a94cf-5924-4d21-acfd-e829cb31769f
[Server] Starting Gitcast API on http://127.0.0.1:8000

[Auth] Session Token: cb7a94cf-5924-4d21-acfd-e829cb31769f
[Server] Starting Gitcast API on http://127.0.0.1:8000
 ██████╗ ██╗████████╗ ██████╗  █████╗  ███████╗████████╗
██╔════╝ ██║╚══██╔══╝██╔════╝ ██╔══██╗ ██╔════╝╚══██╔══╝
██║  ███╗██║   ██║   ██║      ███████║ ███████╗   ██║
██║   ██║██║   ██║   ██║      ██╔══██║ ╚════██║   ██║
╚██████╔╝██║   ██║   ╚██████╗ ██║  ██║ ███████║   ██║
 ╚═════╝ ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝ ╚══════╝   ╚═╝
> [OK] using your configured API keys
[OK] server running at http://localhost:8000
[OK] browser opened
[Trigger] on_trigger fired successfully
[Gitcast] Hotkey fired — starting capture...
[CAPTURE] starting in 5s; switch to target window
  5...
  4...
  3...
  2...
  1...
[CAPTURE] screenshot saved: storage/data/screenshots/capture_20260629_220218.png
[Trigger] capture complete
[OCR] Screenshot file not found: storage/data/screenshots/capture_20260629_220218_framed.png
[Trigger] OCR complete
[Trigger] popup showing
[Gitcast] Mock popup triggered.
[Trigger] raw thought received
[Trigger] Raw thought: 'Captured via hotkey trigger'
[PAYLOAD] image encoding failed: [Errno 2] No such file or directory: 'storage/data/screenshots/capture_20260629_220218_framed.png'
```

### Identified Flaws & Analysis

1. **Screenshot File Path / Relative Paths Issue**:
   * **Problem**: When `gitcast` is run from `snakegame`, the screenshot is generated and saved relative to the package directory (`BASE_DIR` in `context-engine`). However, the OCR step and image payload encoder try to open the screenshot path relative to the current working directory (`CWD` which is `snakegame`), causing `[Errno 2] No such file or directory` errors.
   * **Consequence**: Because image loading fails, the AI only receives a text payload without the screenshot content. Consequently, none of the generated posts mention the visual context of `snakegame`.

2. **Repetitive Browser Tabs Opening on Capture**:
   * **Problem**: Every time a hotkey capture occurs, a browser tab automatically opens `http://localhost:8000`. If a user makes multiple captures during their flow, they end up with many duplicate dashboard tabs opened (e.g. 5+ tabs).
   * **Solution**: A check should be added to avoid opening a new tab if one is already open, or make the opening optional/silenced.

3. **Command & Workflow Confusion**:
   * **Confusion**: Users are confused by the mixing of commands (`gitcast` vs `gitcast capture`) and hotkeys (`Ctrl+Alt+S` / `Ctrl+Shift+P`). Running a command to launch a background server, then needing to press a global OS hotkey to trigger generation, feels like too many disjointed steps.
   * **Solution**: Clean up command-line documentation/triggers and simplify the onboarding flow so that running `gitcast` can directly generate posts or have a unified triggering mechanism.

---

## 5. Duplicate Tab Opening on First Hotkey Trigger - 2026-06-29

### Log Output & Observation
```text
(venv) PS C:\Users\USER\Documents\snakegame> gitcast
> [OK] using your configured API keys
[OK] server running at http://localhost:8000
[OK] browser opened

[Trigger] on_trigger fired successfully
...
[Trigger] got 1 variations
[Trigger] keys: ['linkedin']
[Trigger] linkedin: Just captured a key moment in my Snake Game build ...
[Trigger] opening review window
```

### Identified Flaw & Analysis
* **Problem**: When running `gitcast`, the dashboard is immediately opened in the default browser on startup. However, when the user triggers their very first capture using the `Ctrl+Alt+S` hotkey, the system calls `webbrowser.open("http://localhost:8000")` again. Since the dashboard was already opened at startup, this second call opens a redundant duplicate tab.
* **Solution**: Track whether the browser was already opened at server startup (or set `_browser_opened = True` upon startup in `gitcast.py`), so that the first capture trigger does not open a second browser tab.

---

## 6. Incorrect Post Generation Output with Empty/Thin Context (gitcast==1.0.17) - 2026-07-01

### Issue
When testing `gitcast==1.0.17` on a `snakegame` directory with `raw_thought = "Captured via hotkey trigger"` and no git diff, the generated post repeats/summarizes the prompt structure and priority instructions:

```text
1/3: Context for this build update: Captured via hotkey trigger, priority is determined by git diff, with screen text as secondary context. A hook will be added to enhance functionality.
2/3: If a git diff is present, it serves as the primary source of truth for changes, taking precedence over screen text. The added hook will integrate with this process.
3/3: Final context for build update: Rely on git diff for accurate information on changes, using screen text only for supplementary context, with the new hook providing additional support.
```

### Analysis
Because of the thin context (no git diff, generic thought, and noisy/fragmented OCR), the system instructions, notes, and priority rules leaked into the user message template. Under low-context scenarios, the LLM falls back to summarizing or structuring its response around the prompt meta-instructions rather than writing a real, grounded developer post.

