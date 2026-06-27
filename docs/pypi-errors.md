# PyPI Release & Execution Issues Log

This document records the issues faced during the testing, packaging, and execution of `gitcast` on PyPI, along with their resolutions and current active status.

---

## 1. Resolved Issues

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

### Issue 2.2: ImportError and Pygame conflicts when running gitcast CLI from project directories containing `main.py`
* **Symptom**: Running `gitcast` from any project directory containing its own `main.py` (e.g., `snakegame/main.py`) causes the application to crash on startup after initializing the user's local modules (e.g., importing `pygame` and running game startup logic).
* **Console Logs & Traceback**:
  ```text
  (venv) PS C:\Users\USER\Documents\snakegame> gitcast
  [Monitoring] Sentry not configured - skipping

  [Auth] Session Token: fe45cf73-a93b-4db3-a90a-f03dda41001c
  [Server] Starting Gitcast API on http://127.0.0.1:8000

  [Auth] Session Token: fe45cf73-a93b-4db3-a90a-f03dda41001c
  [Server] Starting Gitcast API on http://127.0.0.1:8000
  pygame 2.6.1 (SDL 2.28.4, Python 3.10.0)
  Hello from the pygame community. https://www.pygame.org/contribute.html
  Traceback (most recent call last):
    File "C:\Users\USER\AppData\Local\Programs\Python\Python310\lib\runpy.py", line 196, in _run_module_as_main
      return _run_code(code, main_globals, None,
    File "C:\Users\USER\AppData\Local\Programs\Python\Python310\lib\runpy.py", line 86, in _run_code
      exec(code, run_globals)
    File "C:\Users\USER\Documents\context-engine\venv\Scripts\gitcast.exe\__main__.py", line 7, in <module>
      sys.exit(main())
    File "C:\Users\USER\Documents\context-engine\venv\lib\site-packages\cli\gitcast.py", line 79, in main
      from main import on_trigger
  ImportError: cannot import name 'on_trigger' from 'main' (C:\Users\USER\Documents\snakegame\main.py)
  ```
* **Root Cause**:
  In `cli/gitcast.py`, the script checks if `main.py` exists in the current working directory (`os.getcwd()`), and if so, prepends `os.getcwd()` to `sys.path` and attempts to run `from main import on_trigger`. 
  This causes the following critical failures:
  1. **Unwanted Side-Effects**: It imports and executes the user's local `main.py` (e.g., in a snake game project), causing dependencies like `pygame` to initialize and boot, printing their community welcome messages and running game startup side-effects.
  2. **Namespace Collision & ImportError**: Since the user's `main.py` does not define `on_trigger`, the application crashes with an `ImportError`.
  3. **Missing Package Module**: The packaged/installed version of `gitcast` from PyPI does not distribute its own root-level `main.py` file because `find_packages()` in `setup.py` only bundles directories containing `__init__.py`. Thus, `main` is completely missing from site-packages.
* **Status**: Logged and pending future resolution.

#### Proposed Solutions & Analysis

##### Option A: Move trigger callback logic to a dedicated package module (e.g., `core/trigger.py`)
* **Rating**: ⭐⭐⭐⭐⭐ (Best Possible Fix)
* **Ups (Pros)**:
  1. **Clean Namespace isolation**: Completely eliminates the custom `sys.path.insert(0, os.getcwd())` lookup logic inside `cli/gitcast.py`.
  2. **No collisions**: Importing from `core.trigger` is guaranteed to load files packaged inside your library's namespace, so it won't conflict with any `main.py` inside the user's workspace.
  3. **No side-effects**: Users' codebases (like a Pygame-based game) will never be imported or executed by Gitcast's boot process.
  4. **Packaging Standard**: Adheres to Python's package guidelines by not polluting the global site-packages namespace with a top-level module named `main`.
* **Downs (Cons)**:
  - Requires moving the `on_trigger` function definition from `main.py` to `core/trigger.py` (minimal effort).

##### Option B: Package the root-level `main.py` explicitly in `setup.py`
* **Rating**: ⭐⭐ (Poor Packaging Practice)
* **Ups (Pros)**:
  - Quick fix: Simply adding `py_modules=["main"]` in `setup.py` distributes `main.py` alongside the package directories.
* **Downs (Cons)**:
  - **Global namespace pollution**: Distributing a generic package module named `main` into Python's `site-packages` namespace is highly discouraged. It will clash with any local `main` module import in users' custom python environments.
  - **Does not solve the collision**: Since `sys.path` in `cli/gitcast.py` checks `os.getcwd()` first, the local `main.py` of the user's project (e.g. `snakegame/main.py`) will still override and take precedence over the packaged `main.py`, preserving the pygame execution side-effects and crash.

