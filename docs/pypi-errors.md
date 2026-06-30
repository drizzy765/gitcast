# PyPI Release & Execution Issues Log

This document records the issues faced during the testing, packaging, and execution of `gitcast` on PyPI, along with their resolutions and current active status.

---

## 1. Resolved Issues

### Fixed in `gitcast==1.0.8`

#### Issue 2.3: Unauthorized (401) API Errors on localhost
* **Symptom**: Browser console logs API call failures: `api/keys/status:1 Failed to load resource: the server responded with a status of 401 (Unauthorized)`.
* **Root Cause**: On page load, the frontend checked if a token existed in `localStorage` and immediately verified it by querying `/api/keys/status`. When the server has restarted or the session has expired, the old token was no longer valid, causing the FastAPI backend to reject it with a `401 Unauthorized` response before the frontend could retrieve a fresh token.
* **Resolution**: Optimized `authGate` in `web/index.html` to check if the app is accessed on `localhost` (using `window.location.hostname`). If so, it auto-fetches the fresh session token directly from the server's `/api/token` endpoint *first* before verifying or falling back to `localStorage`. This avoids sending any request to `/api/keys/status` with an invalid/expired session token on startup, eliminating the console error.

### Fixed in `gitcast==1.0.7`

#### Issue 2.2: ImportError and Pygame conflicts when running gitcast CLI from project directories containing `main.py`
* **Symptom**: Running `gitcast` from any project directory containing its own `main.py` (e.g., `snakegame/main.py`) causes the application to crash on startup after initializing the user's local modules (e.g., importing `pygame` and running game startup logic).
* **Root Cause**: In `cli/gitcast.py`, the script checked if `main.py` existed in the current working directory (`os.getcwd()`), and if so, prepended `os.getcwd()` to `sys.path` and attempted to run `from main import on_trigger`. This executed the user's local `main.py` and crashed when `on_trigger` was not defined.
* **Resolution**: Moved `on_trigger` to `core/trigger.py` and removed all local directory `sys.path` injection.

### Fixed in `gitcast==1.0.6`

#### Issue 1.4: FastAPI Server Rate Limiting on Localhost
* **Symptom**: Browser console logs API call failures when calling `api/article/generate` or other endpoints via the dashboard UI with a 429 Too Many Requests status code.
* **Root Cause**: The FastAPI server used slowapi's default `get_remote_address` rate-limiting key, which rate-limited local requests when they exceeded the threshold (e.g. 5/minute for article generation).
* **Resolution**: Replaced the default `get_remote_address` with a custom `get_client_ip` function in `api/ratelimit.py`. This function returns `None` for any localhost client (`127.0.0.1`, `localhost`, `::1`), which tells slowapi to bypass rate limiting completely for local executions.

#### Issue 1.5: BYOK (Bring Your Own Key) Feature Ignored Authenticated Users
* **Symptom**: When a user logged in via GitHub/Supabase and configured their own provider keys (BYOK), the server would still hit rate limits or token exhaustion on the developer's default keys.
* **Root Cause**: In `api/routes.py`, 19 routes hardcoded `user_id = LOCAL_USER_ID`. This caused the server to completely ignore the user ID of logged-in users, preventing their custom BYOK keys (stored in the Supabase DB) from being resolved and loaded.
* **Resolution**: Updated all 19 endpoints in `api/routes.py` to accept and use the dynamically resolved user ID using FastAPI's dependency injection (`user_id: str = Depends(get_current_user)`). This allows logged-in users to load their custom keys dynamically.

### Fixed in `gitcast==1.0.5`

#### Issue 1.1: Supabase Configuration Load Failure
* **Symptom**: Running `gitcast` from an external directory (e.g. `C:\Users\USER\Documents\snakegame`) outputs:
  ```text
  [STORAGE] Supabase get_posts failed: SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured. Falling back to local JSON.
  ```
* **Root Cause**: The dynamic resolution of `BASE_DIR = Path(__file__).resolve().parent.parent` in `settings.py` evaluated to Python's virtualenv `site-packages/gitcast/` directory rather than the active workspace directory. As a result, the `.env` file containing the Supabase keys was not found.
* **Resolution**: Replaced the direct loading of `BASE_DIR / ".env"` with a multi-path environment file loader. It now searches the following locations in order of priority:
  1. A custom path defined in `GITCAST_ENV_PATH`
  2. The current working directory (`os.getcwd() / ".env"`)
  3. The parent directory of the active virtual environment (`sys.prefix / ".." / ".env"`), resolving to `context-engine/.env`
  4. Standard user directories (`~/.gitcast/.env` and `~/.gitcast.env`)
  5. The fallback package directory (`BASE_DIR / ".env"`)

#### Issue 1.2: UI Settings/BYOK Writes to Package Internals
* **Symptom**: Saving API keys via the dashboard (BYOK feature) or running `gitcast --setup` would write to `site-packages/gitcast/.env`, which was volatile (deleted on package updates) and sometimes generated permission access errors.
* **Resolution**: Updated `api/routes.py` and `cli/gitcast.py` to write to the resolved active `.env` file, falling back to a persistent user-home folder `~/.gitcast/.env` if no local env file existed.

#### Issue 1.3: Package Build Failure (`bdist_wheel` Invalid Command)
* **Symptom**: Attempting to package the build output using `python setup.py sdist bdist_wheel` generated the error:
  ```text
  error: invalid command 'bdist_wheel'
  ```
* **Root Cause**: The `wheel` package was not installed in the python environment, causing `setuptools` to not register the command.
* **Resolution**: Installed `wheel` package (`pip install wheel`) prior to building, enabling setuptools to build the binary wheel package successfully.

---

## 2. Active Issues (To be Addressed)

### Issue 2.1: Post Generation Fails silently (gitcast>=1.0.5)
* **Symptom**: `gitcast` starts up successfully, the FastAPI server listens on `http://127.0.0.1:8000`, the pygame modules load, and the CLI runs, but the application does not generate posts.
* **Console Logs**:
  ```text
  (venv) PS C:\Users\USER\Documents\snakegame> gitcast
  [Monitoring] Sentry not configured - skipping

  [Auth] Session Token: 549cfdc2-c987-416d-8a70-8b0dc5f2315b
  [Server] Starting Gitcast API on http://127.0.0.1:8000

  [Auth] Session Token: 549cfdc2-c987-416d-8a70-8b0dc5f2315b
  [Server] Starting Gitcast API on http://127.0.0.1:8000
  pygame 2.6.1 (SDL 2.28.4, Python 3.10.0)
  Hello from the pygame community. https://www.pygame.org/contribute.html
  ```
* **Status**: Logged and waiting for future triage. The application starts, but key bindings or endpoints triggers are failing to generate the actual post output.

### Issue 2.4: 401 Unauthorized API Errors and Failure to Generate Posts on Directory/Venv Switch (gitcast==1.0.10)
* **Symptom**: Running `gitcast` from a different project directory (`snakegame`) using a different virtual environment leads to `api/keys/status:1 Failed to load resource: 401 (Unauthorized)` in the browser console, and post generation does not trigger.
* **Root Cause**:
  1. **Token Authentication Bypass Failure**: The browser's attempt to retrieve the active session token from `/api/token` returns `403 Forbidden` if the request host is mapped as an IPv4-mapped IPv6 address (e.g. `::ffff:127.0.0.1`). The frontend then falls back to using the old `localStorage` token from a previous run (e.g. in `context-engine`), which the FastAPI backend rejects with a `401 Unauthorized` status.
  2. **Wrong Working Directory Resolution**: If the target directory (`snakegame`) is not a Git repository, `detect_working_directory()` falls back to candidates in the list, matching the parent `context-engine` directory. Diffs and history are scanned from the wrong project, preventing post generation for the active context.
* **Status**: Logged in detail in [pypit-error.md](file:///mnt/c/Users/USER/Documents/context-engine/pypit-error.md) and awaiting resolution.



