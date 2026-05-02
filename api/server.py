import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes import router
from config.settings import missing_api_keys, BASE_DIR, STORAGE_DIR

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Context Engine",
    description="Local AI server for build-in-public post generation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

# allow the UI layer to call the API from localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Relax for local dev
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve storage directory for images
# We mount 'storage' folder which contains 'data/screenshots'
app.mount("/storage", StaticFiles(directory=str(BASE_DIR / "storage")), name="storage")

# register routes
app.include_router(router, prefix="/api")

# Serve Frontend
@app.get("/")
async def read_index():
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


# ── Entry point ───────────────────────────────────────────────────────────────

from api.auth import get_token

def start_server():
    """Starts the FastAPI server. Called from main.py in a background thread."""
    print(f"\n[Auth] Session Token: {get_token()}")
    print("[Server] Starting Context Engine API on http://127.0.0.1:8000")
    uvicorn.run(
        "api.server:app",
        host="127.0.0.1",
        port=8000,
        log_level="warning",  # keep console clean — only show warnings and errors
        reload=False,
    )


if __name__ == "__main__":
    print("[Server] Starting Context Engine API on http://127.0.0.1:8000")
    print("[Server] Docs available at http://127.0.0.1:8000/docs")
    start_server()