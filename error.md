# Error Log Analysis: Supabase URL and Service Key Missing

## Error Details
- **Timestamp**: 14:51:37
- **Severity**: `WARN`
- **Module**: `STORAGE`
- **Message**: `Supabase get_posts failed: SUPABASE_URL and SUPABASE_SERVICE_KEY must be configured. Falling back to local JSON.`

---

## Root Cause Analysis
1. **Directory Resolution**: 
   In [config/settings.py](file:///mnt/c/Users/USER/Documents/context-engine/config/settings.py), `BASE_DIR` is defined dynamically based on the location of `__file__`:
   ```python
   BASE_DIR = Path(__file__).resolve().parent.parent
   ```
2. **Standard vs. Installed Package Behavior**:
   - **Local Development**: When running directly from the project directory, `__file__` is `/mnt/c/Users/USER/Documents/context-engine/config/settings.py`, resolving `BASE_DIR` to the project root. The `.env` file is loaded correctly from `/mnt/c/Users/USER/Documents/context-engine/.env`.
   - **Installed Console Script**: When `gitcast` is installed as a python package (standard non-editable install) and run via `gitcast.exe` under `venv/Scripts/gitcast.exe`, `__file__` resides in `venv/lib/site-packages/config/settings.py`. Thus, `BASE_DIR` resolves to `venv/lib/site-packages/`.
3. **Environment Variable Failure**:
   Because `BASE_DIR` points to `site-packages`, `load_dotenv(BASE_DIR / ".env")` tries to find `.env` inside `venv/lib/site-packages/.env` which does not exist. As a result, `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` remain unconfigured (empty strings), triggering the Supabase initialization runtime error.

---

## Proposed Fix
Modify [config/settings.py](file:///mnt/c/Users/USER/Documents/context-engine/config/settings.py) to fall back to loading the `.env` file from the current working directory (`os.getcwd()`) if the environment variables are not found under `BASE_DIR`. This ensures that when the tool is run from the project root using the installed virtual environment script, it will successfully load the local `.env` variables.
