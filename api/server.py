import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from api.routes import router
from api.auth_routes import router as auth_router
from config.settings import missing_api_keys, BASE_DIR, STORAGE_DIR, CONFIG_DIR
from api.monitoring import init_sentry
from api.ratelimit import limiter
from api.auth import get_token as get_auth_token

# ── App setup ─────────────────────────────────────────────────────────────────

init_sentry()

app = FastAPI(
    title="Gitcast",
    description="Local AI server for build-in-public post generation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    retry_after = 60
    headers = getattr(exc, "headers", None) or {}
    try:
        retry_after = int(headers.get("Retry-After", retry_after))
    except (TypeError, ValueError):
        retry_after = 60
    headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error": "rate limit exceeded",
            "retry_after": retry_after,
            "message": f"[!!] slow down. retry in {retry_after}s.",
        },
        headers=headers,
    )

# allow the UI layer to call the API from localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Relax for local dev
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)

try:
    from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

    app.add_middleware(SentryAsgiMiddleware)
except Exception:
    pass

from pathlib import Path

# create ALL required directories before mounting
_required_dirs = [
    STORAGE_DIR,
    STORAGE_DIR / "screenshots",
    STORAGE_DIR / "drafts",
    STORAGE_DIR / "data",
]
for _dir in _required_dirs:
    _dir.mkdir(parents=True, exist_ok=True)

# now safe to mount
app.mount(
    "/screenshots",
    StaticFiles(
        directory=str(STORAGE_DIR / "screenshots")),
    name="screenshots",
)
app.mount(
    "/storage/data/screenshots",
    StaticFiles(
        directory=str(STORAGE_DIR / "screenshots")),
    name="storage_data_screenshots",
)

app.mount(
    "/assets",
    StaticFiles(directory=str(BASE_DIR / "assets")),
    name="assets",
)


# register routes
app.include_router(router, prefix="/api")
app.include_router(auth_router, prefix="/auth")


# ── Startup Event ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    dirs = [
        STORAGE_DIR,
        STORAGE_DIR / "screenshots",
        STORAGE_DIR / "drafts",
        STORAGE_DIR / "data",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    print("[Server] Storage directories verified")
    print(f"\n[Auth] Session Token: {get_auth_token()}")
    print("[Server] Starting Gitcast API on http://127.0.0.1:8000")


# ── Serve Frontend ────────────────────────────────────────────────────────────

@app.get("/")
async def read_landing():
    return FileResponse(BASE_DIR / "web" / "landing.html")


@app.get("/landing")
async def read_landing_alias():
    return FileResponse(BASE_DIR / "web" / "landing.html")


@app.get("/app")
async def read_app():
    return FileResponse(BASE_DIR / "web" / "index.html")


@app.get("/favicon.ico")
async def favicon():
    return FileResponse(BASE_DIR / "assets" / "favicon.ico")


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
def health_check():
    missing = missing_api_keys()
    return {
        "status": "ok",
        "missing_api_keys": missing,
        "ready": len(missing) == 0,
    }


# ── Auth token retrieval (Localhost only) ───────────────────────────────────────

def is_localhost(host: str) -> bool:
    if not host:
        return False
    clean = host.replace("::ffff:", "")
    return clean in ["127.0.0.1", "::1", "localhost"]

@app.get("/api/token")
async def get_token(request: Request):
    host = request.client.host if request.client else ""
    if not is_localhost(host):
        raise HTTPException(status_code=403,
            detail="localhost only")
    from api.auth import get_token as _get_token
    return {"token": _get_token()}



# ── Entry point ───────────────────────────────────────────────────────────────

def start_server():
    """Starts the FastAPI server. Called from main.py in a background thread."""
    # Write session token to config/session_token.txt
    try:
        token_file = CONFIG_DIR / "session_token.txt"
        token_file.write_text(get_auth_token(), encoding="utf-8")
    except Exception as e:
        print(f"[Server] Failed to write session token to file: {e}")

    print(f"\n[Auth] Session Token: {get_auth_token()}")
    print("[Server] Starting Gitcast API on http://127.0.0.1:8000")
    uvicorn.run(
        "api.server:app",
        host="127.0.0.1",
        port=8000,
        log_level="warning",  # keep console clean — only show warnings and errors
        reload=False,
    )


if __name__ == "__main__":
    print("[Server] Starting Gitcast API on http://127.0.0.1:8000")
    print("[Server] Docs available at http://127.0.0.1:8000/docs")
    start_server()
