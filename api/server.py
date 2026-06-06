import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from api.routes import router
from api.auth_routes import router as auth_router
from config.settings import missing_api_keys, BASE_DIR, STORAGE_DIR, CONFIG_DIR
from api.monitoring import init_sentry
from api.ratelimit import limiter

# ── App setup ─────────────────────────────────────────────────────────────────

init_sentry()

app = FastAPI(
    title="Shiplog",
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

# Serve storage directory for images
# We mount 'storage' folder which contains 'data/screenshots'
app.mount("/storage", StaticFiles(directory=str(BASE_DIR / "storage")), name="storage")

# register routes
app.include_router(router, prefix="/api")
app.include_router(auth_router, prefix="/auth")

# Serve Frontend
@app.get("/")
async def read_landing():
    return FileResponse(BASE_DIR / "web" / "landing.html")


@app.get("/landing")
async def read_landing_alias():
    return FileResponse(BASE_DIR / "web" / "landing.html")


@app.get("/app")
async def read_app():
    return FileResponse(BASE_DIR / "web" / "index.html")


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

from api.auth import get_token

@app.get("/api/token")
def get_session_token(request: Request):
    client_host = request.client.host if request.client else None
    if client_host not in ["127.0.0.1", "localhost", "::1"]:
        raise HTTPException(status_code=403, detail="Forbidden: Access allowed only from localhost")
    return {"token": get_token()}


# ── Entry point ───────────────────────────────────────────────────────────────

def start_server():
    """Starts the FastAPI server. Called from main.py in a background thread."""
    # Write session token to config/session_token.txt
    try:
        token_file = CONFIG_DIR / "session_token.txt"
        token_file.write_text(get_token(), encoding="utf-8")
    except Exception as e:
        print(f"[Server] Failed to write session token to file: {e}")

    print(f"\n[Auth] Session Token: {get_token()}")
    print("[Server] Starting Shiplog API on http://127.0.0.1:8000")
    uvicorn.run(
        "api.server:app",
        host="127.0.0.1",
        port=8000,
        log_level="warning",  # keep console clean — only show warnings and errors
        reload=False,
    )


if __name__ == "__main__":
    print("[Server] Starting Shiplog API on http://127.0.0.1:8000")
    print("[Server] Docs available at http://127.0.0.1:8000/docs")
    start_server()
